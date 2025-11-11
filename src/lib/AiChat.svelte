<script lang="ts">
  // ============================================================================
  // IMPORTS AND DEPENDENCIES
  // ============================================================================
  import { onMount, tick } from 'svelte';
  import { get } from 'svelte/store';
  import { connectWebSocket, sendChatMessage, sendWorkflow } from '$lib/api';
  import { dslCode } from '$lib/stores/dslStore';
  import DataTable from '$lib/DataTable.svelte';
  import { tableRegistry } from '$lib/stores/tableRegistry';

  // NEW: session store
  import {
    sessions, currentSessionId, messages,
    ensureSession, createSession, switchSession, deleteSession, renameSession,
    appendMessage, updateMessageById, type Message as ChatMsg
  } from '$lib/chat/sessionStore';

  // ============================================================================
  // COMPONENT PROPS AND CONFIGURATION
  // ============================================================================
  export let height: string = '96vh';

  // ============================================================================
  // REACTIVE VARIABLES AND STATE MANAGEMENT
  // ============================================================================
  let userMessage = '';
  let messagesContainer: HTMLDivElement | null = null;

  // rename UI
  let renamingId: string | null = null;
  let renameText = '';

  // ============================================================================
  // LIFECYCLE HOOKS
  // ============================================================================
  let wsConnectionRetries = 0;
  const maxRetries = 5;
  let wsListenerSetup = false;
  
  onMount(() => {
    ensureSession();
    if (!wsListenerSetup) {
      connectWS();
      wsListenerSetup = true;
    }
    scrollToBottomSoon();
    
    // Cleanup on unmount
    return () => {
      wsListenerSetup = false;
    };
  });

  // ============================================================================
  // WEBSOCKET COMMUNICATION
  // ============================================================================
  function connectWS() {
    console.log('[AiChat] Setting up WebSocket listener...');
    connectWebSocket((data: any) => {
      // Reset retry counter on successful message
      wsConnectionRetries = 0;
      
      // 1) append assistant message to current session
      const text = data.message ?? JSON.stringify(data);
      const assistantMsg = appendMessage('assistant', text, { tableData: data.tableData });

      // 2) table payload direct
      if (data.tableData?.length) {
        tableRegistry.save(assistantMsg.id, data.tableData);
      }

      // 3) parse "Results:" in message text
      handleQueryResponse(assistantMsg);
      scrollToBottomSoon();
    });
  }

  // ============================================================================
  // DSL RULE EXTRACTION
  // ============================================================================
  function extractRuleFromDSL(dsl: string, ruleCode: string): any | null {
    // Try to find a rule with matching rule_code in the DSL
    const lines = dsl.split('\n');
    let inRulesSection = false;
    let currentRule: any = null;
    let captureLogic = false;
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();
      
      // Check if we're in RULES section
      if (trimmed === 'RULES:' || trimmed.startsWith('RULES:')) {
        inRulesSection = true;
        continue;
      }
      
      // Exit RULES section if we hit another major section
      if (inRulesSection && /^[A-Z]+:/.test(trimmed) && trimmed !== 'RULES:') {
        inRulesSection = false;
        break;
      }
      
      if (inRulesSection) {
        // Check for new rule item (starts with -)
        if (trimmed.startsWith('- rule_code:') || trimmed === '-') {
          // Save previous rule if we had one that matches
          if (currentRule && currentRule.rule_code === ruleCode) {
            return currentRule;
          }
          currentRule = null; // Reset for new rule
          
          // Check if rule_code is on the same line as dash
          if (trimmed.startsWith('- rule_code:')) {
            const code = trimmed.replace('- rule_code:', '').trim().replace(/["']/g, '');
            if (code === ruleCode) {
              currentRule = { rule_code: ruleCode };
            }
          }
        }
        // Also check for rule_code on next line after dash
        else if (trimmed.startsWith('rule_code:') && !currentRule) {
          const code = trimmed.replace('rule_code:', '').trim().replace(/["']/g, '');
          if (code === ruleCode) {
            currentRule = { rule_code: ruleCode };
          }
        }
        
        // Capture rule details if we have a matching rule
        if (currentRule) {
          if (trimmed.startsWith('severity:')) {
            currentRule.severity = trimmed.replace('severity:', '').trim().replace(/["']/g, '');
          } else if (trimmed.startsWith('message:')) {
            currentRule.message = trimmed.replace('message:', '').trim().replace(/["']/g, '');
          } else if (trimmed.startsWith('description:')) {
            // Description might be multi-line
            const descStart = line.indexOf('description:') + 'description:'.length;
            currentRule.description = line.substring(descStart).trim();
            // Check next lines for continued description
            let j = i + 1;
            while (j < lines.length && lines[j].match(/^\s+/) && !lines[j].trim().includes(':')) {
              currentRule.description += ' ' + lines[j].trim();
              j++;
            }
          } else if (trimmed.startsWith('logic:')) {
            // Logic might be on the same line or next line
            const logicStart = line.indexOf('logic:') + 'logic:'.length;
            const inlineLogic = line.substring(logicStart).trim();
            if (inlineLogic) {
              currentRule.logic = inlineLogic;
            } else {
              // Check next line for logic
              if (i + 1 < lines.length) {
                currentRule.logic = lines[i + 1].trim();
              }
            }
          }
        }
      }
    }
    
    // Return the last rule if it matches
    if (currentRule && currentRule.rule_code === ruleCode) {
      console.log('[extractRuleFromDSL] Found rule:', currentRule);
      return currentRule;
    }
    
    console.log('[extractRuleFromDSL] Rule not found:', ruleCode);
    return null;
  }

  // ============================================================================
  // MESSAGE HANDLING AND SENDING
  // ============================================================================
  async function sendMessage(): Promise<void> {
    const prompt = userMessage.trim();
    const currentDsl = (get(dslCode) ?? '').trim();

    if (!prompt) return;
    if (!currentDsl) {
      console.warn('DSL is empty - please load or type DSL before sending.');
      appendMessage('assistant', 'Please load a DSL program in the Code tab first.');
      scrollToBottomSoon();
      return;
    }

    appendMessage('user', prompt);
    
    try {
      // Send everything as natural language - let the backend LLM handle intent
      console.log('[sendMessage] Sending natural language to backend:', prompt);
      const message_id = `msg_${Date.now()}`;
      await sendChatMessage(
        `NATURAL_LANGUAGE:${prompt}\nDSL:${currentDsl}`, 
        'Process natural language input',
        message_id
      );
    } catch (error) {
      console.error('[sendMessage] Error sending message:', error);
      appendMessage('assistant', 'Error connecting to the backend. Please ensure the server is running.');
    }

    userMessage = '';
    scrollToBottomSoon();
  }

  // ============================================================================
  // RESPONSE PROCESSING AND TABLE DATA EXTRACTION
  // ============================================================================
  function handleQueryResponse(msg: ChatMsg): void {
    const chatText = msg.text;
    const m = /results\s*:/i.exec(chatText);
    if (!m) return;

    const ix = m.index;
    const queryText = chatText.slice(0, ix).trim();
    let rawResults = chatText.slice(ix + m[0].length).trim();

    const fence = rawResults.match(/```(?:json|sql)?\s*([\s\S]*?)```/i);
    if (fence) rawResults = fence[1].trim();

    const jsonContent = extractJsonLikeContent(rawResults);
    let parsed: any = null;
    try { parsed = JSON.parse(jsonContent); }
    catch {
      if (/^[\[{].*[\]}]$/.test(jsonContent)) {
        const softened = jsonContent
          .replace(/([{,]\s*)'([^']+?)'\s*:/g, '$1"$2":')
          .replace(/:\s*'([^']*?)'(\s*[},])/g, ':"$1"$2');
        try { parsed = JSON.parse(softened); } catch {}
      }
    }
    if (parsed == null) return;

    const tableRows = normalizeToTableRows(parsed);
    if (tableRows?.length) {
      updateMessageById(msg.id, { text: queryText, tableData: tableRows });
      tableRegistry.save(msg.id, tableRows);
    }
  }

  function extractJsonLikeContent(s: string): string {
    if (/^\s*[\[{]/.test(s)) return s;
    const start = s.search(/[\[{]/); if (start === -1) return s;
    const open = s[start]; const close = open === '{' ? '}' : ']';
    let depth = 0;
    for (let i = start; i < s.length; i++) {
      const ch = s[i];
      if (ch === open) depth++;
      else if (ch === close) { depth--; if (depth === 0) return s.slice(start, i+1).trim(); }
    }
    return s.slice(start).trim();
  }

  function normalizeToTableRows(parsed: any): Array<Record<string, any>> | null {
    // 1) array of objects
    if (Array.isArray(parsed) && parsed.length && typeof parsed[0] === 'object' && parsed[0] !== null && !Array.isArray(parsed[0])) {
      return parsed as Array<Record<string, any>>;
    }
    // 2) { columns, rows }
    if (parsed?.columns && Array.isArray(parsed.columns) && Array.isArray(parsed.rows)) {
      const cols: string[] = parsed.columns;
      return (parsed.rows as any[][]).map(r => Object.fromEntries(cols.map((c: string, i: number) => [c, r[i]])));
    }
    // 3) [ [headers...], [row...], ... ]
    if (Array.isArray(parsed) && parsed.length > 1 && Array.isArray(parsed[0]) && parsed[0].every((h: any)=>typeof h==='string')) {
      const headers: string[] = parsed[0];
      return (parsed.slice(1) as any[][]).map(r => Object.fromEntries(headers.map((h, i)=>[h, r[i]])));
    }
    return null;
  }

  // ============================================================================
  // UI INTERACTION HANDLERS
  // ============================================================================
  function escapeHtml(unsafe: string): string {
    return unsafe
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
  function handleTextareaResize(event: Event): void {
    const textarea = event.target as HTMLTextAreaElement;
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
  }

  function handleKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  async function scrollToBottomSoon() {
    await tick();
    if (!messagesContainer) return;
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function startRename(id: string, current: string) { renamingId = id; renameText = current; }
  function commitRename(id: string) {
    if (renameText.trim()) renameSession(id, renameText.trim());
    renamingId = null;
  }
</script>

<!-- ============================================================================
     TEMPLATE MARKUP
     ============================================================================ -->
<div class="layout" style="height:{height}">
  <!-- LEFT: sessions -->
  <aside class="sessions">
    <div class="sessions__header">
      <div class="heading heading_5">Chats</div>
      <button class="btn" on:click={() => switchSession(createSession('New Chat').id)}>+ New</button>
    </div>

    {#each $sessions as s}
      <div class="session { $currentSessionId === s.id ? 'session--active' : '' }">
        {#if renamingId === s.id}
          <input
            class="session__rename"
            bind:value={renameText}
            on:keydown={(e)=> e.key==='Enter' && commitRename(s.id)}
            on:blur={() => commitRename(s.id)}
            autofocus
          />
        {:else}
          <button class="session__title" on:click={() => switchSession(s.id)} title={new Date(s.updatedAt).toLocaleString()}>
            {s.title}
          </button>
          <div class="session__actions">
            <button title="Rename" on:click={() => startRename(s.id, s.title)}>✏️</button>
            <button title="Delete" on:click={() => deleteSession(s.id)}>🗑️</button>
          </div>
        {/if}
      </div>
    {/each}
  </aside>

  <!-- RIGHT: chat panel -->
  <section class="chat">
    <div class="chat-messages" bind:this={messagesContainer}>
      <div class="heading heading_4 mb-2">AI Chat Assistant</div>

      {#each $messages as message}
        <div class="message-container {message.sender}">
          <div class="message-bubble">
            <div class="message-sender">{message.sender === 'user' ? 'You' : 'Denise'}</div>
            <div class="message-text">{@html message.sender === 'user' ? escapeHtml(message.text) : message.text}</div>

            {#if message.tableData && message.tableData.length}
              <div class="table-container">
                <DataTable
                  tableId={message.id}
                  options={{ pageLength: 10, lengthChange: false, ordering: true }}
                />
              </div>
            {/if}
          </div>
        </div>
      {/each}
    </div>

    <div class="chat-input">
      <div class="input">
        <textarea
          class="input__text"
          class:input__text_changed={userMessage.length > 0}
          bind:value={userMessage}
          rows="1"
          style="max-height: 200px; overflow-y: auto;"
          on:input={handleTextareaResize}
          on:keydown={handleKeyDown}
          placeholder=""
        ></textarea>
        <label class="input__label">Ask something</label>
      </div>
    </div>
  </section>
</div>

<!-- ============================================================================
     STYLES
     ============================================================================ -->
  <style>
      .layout {
        display: grid;
        grid-template-columns: 260px 1fr;
        /* ensure the single row can shrink so children can scroll */
        grid-template-rows: 1fr;
        background:#fff;
        /* you already set a style="height:{height}" inline */
      }
    
      .sessions {
        border-right:1px solid #e4e6eb;
        padding: .75rem;
        overflow:auto;
        /* allow grid item to shrink horizontally if needed */
        min-width: 0;
      }
    
      /* KEY: grid item must allow its flex children to overflow/scroll */
      .chat {
        display:flex;
        flex-direction:column;
        min-height: 0;         /* <-- important in grid context */
      }
    
      .chat-messages {
        flex: 1 1 auto;        /* fill remaining space */
        min-height: 0;         /* allow this area to actually scroll */
        overflow-y: auto;      /* scrolling happens here */
        padding:1rem;
        display:flex;
        flex-direction:column;
        gap:.75rem;
      }
    
      /* keep the input pinned; don’t let it shrink */
      .chat-input {
        flex: 0 0 auto;        /* <-- fixed at the bottom */
        padding:1rem;
        border-top:1px solid #e4e6eb;
        background:#fff;
      }
    
      .message-container { display:flex; width:100%; }
      .message-container.user { justify-content:flex-end; }
      .message-container.assistant { justify-content:flex-start; }
    
      .message-bubble {
        max-width:90%;
        padding: .75rem 1rem;
        border-radius:1rem;
        position:relative;
        word-wrap:break-word;
        white-space: pre-wrap;
        box-shadow:0 1px 2px rgba(0,0,0,0.1);
      }
    
      .message-container.user .message-bubble {
        background:#0084ff; color:#fff; border-bottom-right-radius:.25rem;
      }
      .message-container.assistant .message-bubble {
        background:#fff; color:#050505; border-bottom-left-radius:.25rem; border:1px solid #e4e6eb;
      }
    
      .message-sender { font-weight:600; font-size:.8rem; margin-bottom:.25rem; }
      .message-container.user .message-sender { color:rgba(255,255,255,.8); }
      .message-container.assistant .message-sender { color:#65676b; }
    
      /* HTML content styling in messages */
      .message-text :global(h1),
      .message-text :global(h2),
      .message-text :global(h3),
      .message-text :global(h4),
      .message-text :global(h5),
      .message-text :global(h6) {
        margin-top: 0.5em;
        margin-bottom: 0.5em;
      }
      
      .message-text :global(p) {
        margin: 0.5em 0;
      }
      
      .message-text :global(ul),
      .message-text :global(ol) {
        margin: 0.5em 0;
        padding-left: 1.5em;
      }
      
      .message-text :global(li) {
        margin: 0.25em 0;
      }
      
      .message-text :global(code) {
        background-color: #f0f0f0;
        padding: 0.125em 0.25em;
        border-radius: 0.25em;
        font-family: monospace;
        font-size: 0.9em;
      }
      
      .message-text :global(pre) {
        background-color: #f0f0f0;
        padding: 0.5em;
        border-radius: 0.5em;
        overflow-x: auto;
      }
      
      .message-text :global(pre code) {
        background-color: transparent;
        padding: 0;
      }
      
      .message-text :global(strong) {
        font-weight: 600;
      }
      
      .message-text :global(em) {
        font-style: italic;
      }
      
      .message-text :global(blockquote) {
        border-left: 3px solid #ccc;
        padding-left: 1em;
        margin: 0.5em 0;
        color: #666;
      }
      
      .message-text :global(table) {
        border-collapse: collapse;
        width: 100%;
        margin: 0.5em 0;
      }
      
      .message-text :global(th),
      .message-text :global(td) {
        border: 1px solid #ddd;
        padding: 0.5em;
        text-align: left;
      }
      
      .message-text :global(th) {
        background-color: #f5f5f5;
        font-weight: 600;
      }
    
      .table-container {
        margin-top:.75rem;
        border:1px solid #e0e0e0;
        border-radius:8px;
        box-shadow:0 1px 3px rgba(0,0,0,.1);
      }
    
      /* sessions panel bits */
      .sessions__header { display:flex; justify-content:space-between; align-items:center; margin-bottom:.5rem; }
      .btn { border:1px solid #e4e6eb; border-radius:.5rem; padding:.25rem .5rem; background:#fff; }
      .session { display:flex; align-items:center; justify-content:space-between; gap:.5rem; padding:.25rem .25rem; border-radius:.5rem; }
      .session--active { background:#f3f4f6; }
      .session__title { text-align:left; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .session__rename { width:100%; }
      .session__actions button { opacity:.7; }
      .session__actions button:hover { opacity:1; }
    </style>
    
