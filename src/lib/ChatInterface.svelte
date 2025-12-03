<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import ChatMessage from './ChatMessage.svelte';
	import ChatInput from './ChatInput.svelte';

	interface Message {
		id: string;
		role: 'user' | 'agent';
		content: string;
		timestamp: Date;
		envelopeData?: {
			decision?: string;
			confidence?: number;
			reason?: string;
			nextAgent?: string | null;
			returnCode?: number;
		};
	}

	let messages: Message[] = [];
	let isLoading = false;
	let messagesContainer: HTMLDivElement;
	let messageCounter = 0;
	let websocket: WebSocket | null = null;
	let connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error' = 'disconnected';
	let connectionError: string = '';
	let sessionId: string = '';
	let requestCounter = 0;

	export let onClose = () => {};

	const WS_URL = 'ws://localhost:8000/ws';

	onMount(() => {
		sessionId = `session-${Math.random().toString(36).slice(2, 9)}`;
		connectWebSocket();
		// Auto-scroll to bottom when component mounts
		scrollToBottom();
	});

	onDestroy(() => {
		if (websocket) {
			websocket.close();
		}
	});

	function connectWebSocket() {
		try {
			connectionStatus = 'connecting';
			connectionError = '';
			
			websocket = new WebSocket(WS_URL);

			websocket.onopen = () => {
				connectionStatus = 'connected';
				console.log('WebSocket connected to Pitboss');
				addSystemMessage('Connected to Pattern Agent');
			};

			websocket.onmessage = (event) => {
				try {
					const data = JSON.parse(event.data);
					handleWebSocketMessage(data);
				} catch (e) {
					console.error('Failed to parse WebSocket message:', e);
				}
			};

			websocket.onerror = (event) => {
				connectionStatus = 'error';
				connectionError = 'WebSocket connection error';
				console.error('WebSocket error:', event);
				isLoading = false;
			};

			websocket.onclose = () => {
				connectionStatus = 'disconnected';
				console.log('WebSocket disconnected');
				isLoading = false;
			};
		} catch (e) {
			connectionStatus = 'error';
			connectionError = `Failed to connect: ${e}`;
			console.error('WebSocket connection failed:', e);
		}
	}

	function handleWebSocketMessage(data: any) {
		isLoading = false;
		
		// New Message Protocol (v1.1)
		if (data.type === 'response' || data.type === 'error') {
			const decision = data.decision ? `[${String(data.decision).toUpperCase()}]` : '';
			const confidence = typeof data.confidence === 'number' ? ` (${Math.round(data.confidence * 100)}%)` : '';
			const reason = data.reason ? `\n${data.reason}` : '';
			const nextAgent = data.nextAgent ? `\nNext: ${data.nextAgent}` : '';
			
			const content = `${decision}${confidence}${reason}${nextAgent}`;
			
			const agentMessage: Message = {
				id: `msg-${++messageCounter}`,
				role: 'agent',
				content: content || data.reason || '...',
				timestamp: new Date(),
				envelopeData: {
					decision: data.decision,
					confidence: data.confidence,
					reason: data.reason,
					nextAgent: data.nextAgent,
					returnCode: data.returnCode
				}
			};
			messages = [...messages, agentMessage];
			scrollToBottom();
			
			// HITL: Stop if decision is 'no'
			if (data.decision === 'no') {
				isLoading = false;
			}
		}
		// Legacy protocol
		else if (data.type === 'rule_result') {
			const agentMessage: Message = {
				id: `msg-${++messageCounter}`,
				role: 'agent',
				content: data.message,
				timestamp: new Date()
			};
			messages = [...messages, agentMessage];
			scrollToBottom();
    } else if (data.type === 'error') {
        const errorMessage: Message = {
            id: `msg-${++messageCounter}`,
            role: 'agent',
            content: `❌ Error: ${data.message}`,
            timestamp: new Date()
        };
        messages = [...messages, errorMessage];
        scrollToBottom();
    } else if (data.type === 'event' && data.event === 'views:refresh') {
        // Notify other parts of the app (e.g., Sidebar) to refresh views list
        window.dispatchEvent(new CustomEvent('views:refresh', { detail: data.payload }));
    }
}

	function addSystemMessage(content: string) {
		const msg: Message = {
			id: `msg-${++messageCounter}`,
			role: 'agent',
			content,
			timestamp: new Date()
		};
		messages = [...messages, msg];
		scrollToBottom();
	}

	function scrollToBottom() {
		if (messagesContainer) {
			setTimeout(() => {
				messagesContainer.scrollTop = messagesContainer.scrollHeight;
			}, 0);
		}
	}

	async function handleSendMessage(message: string) {
		// Add user message
		const userMessage: Message = {
			id: `msg-${++messageCounter}`,
			role: 'user',
			content: message,
			timestamp: new Date()
		};

		messages = [...messages, userMessage];
		scrollToBottom();

		if (connectionStatus === 'connected' && websocket) {
			isLoading = true;
			
			try {
				// Send via new Message Protocol (v1.1)
				// Use GENERIC verb to let LanguageCapo determine if it's RULE or CONTENT
				const requestId = `req-${++requestCounter}`;
				const request = {
					type: 'request',
					version: '1.1',
					timestamp: Date.now(),
					session_id: sessionId,
					request_id: requestId,
					verb: 'GENERIC',
					nextAgent: 'model.LanguageCapo',
					returnCode: 0,
					decision: null,
					confidence: 0.0,
					reason: '',
					messageBody: {
						raw_text: message
					}
				};
				
				console.log('Sending envelope:', request);
				websocket.send(JSON.stringify(request));
				// Response envelopes will come via onmessage handler
			} catch (e) {
				isLoading = false;
				console.error('Failed to send message:', e);
				const errorMessage: Message = {
					id: `msg-${++messageCounter}`,
					role: 'agent',
					content: `❌ Failed to send request: ${e}`,
					timestamp: new Date()
				};
				messages = [...messages, errorMessage];
				scrollToBottom();
			}
		} else {
			isLoading = false;
			const statusMsg = connectionStatus === 'connected' ? 'WebSocket not ready' : `Not connected (status: ${connectionStatus})`;
			const errorMessage: Message = {
				id: `msg-${++messageCounter}`,
				role: 'agent',
				content: `❌ ${statusMsg}`,
				timestamp: new Date()
			};
			messages = [...messages, errorMessage];
			scrollToBottom();
		}
	}

	function clearChat() {
		messages = [];
		messageCounter = 0;
	}
</script>

<div class="chat-interface">
	<div class="chat-header">
		<div class="chat-header-title">
			<h2 class="chat-title">Pattern Agent</h2>
			<div class="connection-status" class:connected={connectionStatus === 'connected'} class:error={connectionStatus === 'error'} title="Connection status: {connectionStatus}">
				<span class="status-dot"></span>
				<span class="status-text">{connectionStatus}</span>
			</div>
		</div>
		<div class="chat-header-actions">
			<button class="clear-button" on:click={clearChat} title="Clear conversation">
				<i class="material-icons">delete_sweep</i>
			</button>
			<button class="close-button" on:click={onClose} title="Close chat">
				<i class="material-icons">close</i>
			</button>
		</div>
	</div>

	<div class="messages-container" bind:this={messagesContainer}>
		{#if messages.length === 0}
			<div class="empty-state">
				<i class="material-icons">chat_bubble_outline</i>
				<p>Start a conversation with the Pattern Agent</p>
			</div>
		{/if}

		{#each messages as message (message.id)}
			<ChatMessage
				role={message.role}
				content={message.content}
				timestamp={message.timestamp}
			/>
		{/each}

		{#if isLoading}
			<div class="agent-typing">
				<div class="typing-indicator">
					<span></span>
					<span></span>
					<span></span>
				</div>
			</div>
		{/if}
	</div>

	<ChatInput {isLoading} onSend={handleSendMessage} />
</div>

<style>
	.chat-interface {
		display: flex;
		flex-direction: column;
		height: 100%;
		background-color: #fff;
		border-radius: 8px;
		overflow: hidden;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
	}

	.chat-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1rem;
		border-bottom: 1px solid #e0e0e0;
		background-color: #fafafa;
	}

	.chat-header-title {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.chat-title {
		margin: 0;
		font-size: 1.1rem;
		font-weight: 500;
		color: rgba(0, 0, 0, 0.87);
	}

	.connection-status {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.75rem;
		color: rgba(0, 0, 0, 0.54);
		padding: 0.25rem 0.5rem;
		border-radius: 12px;
		background-color: rgba(0, 0, 0, 0.05);
		text-transform: capitalize;
	}

	.connection-status.connected {
		color: #4CAF50;
		background-color: rgba(76, 175, 80, 0.1);
	}

	.connection-status.error {
		color: #f44336;
		background-color: rgba(244, 67, 54, 0.1);
	}

	.status-dot {
		display: inline-block;
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background-color: rgba(0, 0, 0, 0.54);
	}

	.connection-status.connected .status-dot {
		background-color: #4CAF50;
		animation: pulse 2s infinite;
	}

	.connection-status.error .status-dot {
		background-color: #f44336;
	}

	@keyframes pulse {
		0%, 100% {
			opacity: 1;
		}
		50% {
			opacity: 0.5;
		}
	}

	.status-text {
		font-weight: 500;
	}

	.chat-header-actions {
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.clear-button,
	.close-button {
		background: none;
		border: none;
		cursor: pointer;
		padding: 0.5rem;
		border-radius: 4px;
		display: flex;
		align-items: center;
		justify-content: center;
		color: rgba(0, 0, 0, 0.54);
		transition: all 0.2s ease;
	}

	.clear-button:hover,
	.close-button:hover {
		background-color: rgba(0, 0, 0, 0.08);
		color: rgba(0, 0, 0, 0.87);
	}

	.clear-button i,
	.close-button i {
		font-size: 20px;
	}

	.messages-container {
		flex: 1;
		overflow-y: auto;
		padding: 1rem;
		background-color: #fff;
	}

	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		height: 100%;
		color: rgba(0, 0, 0, 0.38);
		text-align: center;
		gap: 1rem;
	}

	.empty-state i {
		font-size: 48px;
		opacity: 0.5;
	}

	.empty-state p {
		margin: 0;
		font-size: 0.9375rem;
	}

	.agent-typing {
		display: flex;
		align-items: center;
		margin: 0.75rem 0;
	}

	.typing-indicator {
		display: flex;
		gap: 0.25rem;
		padding: 0.75rem 1rem;
		background-color: #f5f5f5;
		border-radius: 12px;
		border-bottom-left-radius: 4px;
	}

	.typing-indicator span {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background-color: rgba(0, 0, 0, 0.54);
		animation: bounce 1.4s infinite;
	}

	.typing-indicator span:nth-child(1) {
		animation-delay: 0s;
	}

	.typing-indicator span:nth-child(2) {
		animation-delay: 0.2s;
	}

	.typing-indicator span:nth-child(3) {
		animation-delay: 0.4s;
	}

	@keyframes bounce {
		0%,
		60%,
		100% {
			transform: translateY(0);
			opacity: 0.7;
		}
		30% {
			transform: translateY(-10px);
			opacity: 1;
		}
	}

	/* Scrollbar styling */
	.messages-container::-webkit-scrollbar {
		width: 6px;
	}

	.messages-container::-webkit-scrollbar-track {
		background: transparent;
	}

	.messages-container::-webkit-scrollbar-thumb {
		background-color: rgba(0, 0, 0, 0.2);
		border-radius: 3px;
	}

	.messages-container::-webkit-scrollbar-thumb:hover {
		background-color: rgba(0, 0, 0, 0.4);
	}
</style>
