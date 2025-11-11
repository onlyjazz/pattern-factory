import { selectedStudy } from '$lib/selectedStudy';
import { get } from 'svelte/store';
import axios from 'axios';
import type { Study } from '$lib/stores/studies';

export interface Alert {
  subjid: string;
  protocol_id: string;
  crf: string;
  variable: string;
  variable_value: number;
  rule_id: string;
  status: number;
  date_created: string; // ISO timestamp
}

export interface Card {
  sponsor: string;
  protocol_id: string;
  prompt: string;
  agent: string;
  date_created: string; // ISO timestamp
  date_amended: string; // ISO timestamp
}

export async function addStudy(study: Study): Promise<void> {
  const now = new Date().toISOString();

  const payload = {
    protocol_id: study.name,
    sponsor: study.customer,
    description: study.code || '',
    date_created: now,
    date_amended: now
  };

  const response = await fetch('http://localhost:8000/add_protocol', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to add study');
  }
}


export async function getAlerts() {
  const protocol_id = get(selectedStudy)?.name;
  try {
    const response = await axios.get("http://localhost:8000/get_alerts", {
      params: { protocol_id }
    });
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 500) {
        console.error('Server error while fetching alerts. The server might be experiencing issues.');
        // Return an empty array as a fallback
        return [];
      }
      console.error('Error fetching alerts:', error.message);
    } else {
      console.error('An unexpected error occurred:', error);
    }
    // Re-throw the error if it's not a 500 error
    throw error;
  }
}

export async function fetchDDTItems() {
  const protocol_id = get(selectedStudy)?.name;
  try {
    const response = await fetch(`http://localhost:8000/read_ddt_items?protocol_id=${protocol_id}`);
    if (!response.ok) throw new Error(`Error: ${response.statusText}`);
    return await response.json();
  } catch (error) {
    console.error('Error fetching DDT items:', error);
    return [];
  }
}


export async function fetchProtocols() {
    try {
        const response = await fetch("http://localhost:8000/get_protocols");
        if (!response.ok) throw new Error(`Error: ${response.statusText}`);
        const protocols = await response.json();
        return protocols.map((p: any) => ({
            protocol_id: p.protocol_id,
            sponsor: p.sponsor,
            rules: 0, // This would need to be fetched separately if needed
            description: p.description,
            data: p.date_created.split('T')[0], // Format date as YYYY-MM-DD
            status: 'Active', // Default status
            selected: false
        }));
    } catch (error) {
        console.error('Error fetching protocols:', error);
        return [];
    }
}

// Fetch the rules
export async function fetchRules() {
  const protocol_id = get(selectedStudy)?.name;
  try {
    const res = await fetch(`http://localhost:8000/get_rules?protocol_id=${protocol_id}`);
    if (!res.ok) throw new Error(`Error: ${res.statusText}`);
    const rules = await res.json();
    return rules.map((r: any) => ({
      rule_id: r.rule_id,
      protocol_id: r.protocol_id,
      sponsor: r.sponsor,
      rule_code: r.rule_code,
      date_created: r.date_created,
      date_amended: r.date_amended
    }));
  } catch (error) {
    console.error('Error fetching rules:', error);
    return [];
  }
}


// Takes rules from codemirror block and adds/removes rules in the database
export async function sendRulesFromDSL(dslBlock: string) {
  const currentStudy = get(selectedStudy);
  const protocol_id = currentStudy?.name;
  const sponsor = currentStudy?.customer;

  if (!protocol_id || !sponsor) {
    return { success: false, message: 'No protocol or sponsor selected.' };
  }

  const timestamp = new Date().toISOString();

  // Fetch existing rules
  let existingRules: Array<{ rule_id: string, rule_code: string }> = [];
  try {
    const res = await fetch(`http://localhost:8000/get_rules?protocol_id=${protocol_id}`);
    if (res.ok) {
      const data = await res.json();
      existingRules = data
        .filter((rule: any) => rule.protocol_id === protocol_id)
        .map((rule: any) => ({
          rule_id: rule.rule_id,
          rule_code: rule.rule_code.trim()
        }));
    }
  } catch (err) {
    console.warn('Could not fetch existing rules. Proceeding anyway.');
  }

  // Prepare trimmed full block
  const newRuleCode = dslBlock.trim();

  // Check if it's already stored
  const alreadyExists = existingRules.some(r => r.rule_code === newRuleCode);

  if (alreadyExists) {
    return { success: true, message: 'Rule already exists.' };
  }

  // Remove all existing rules for this protocol (optional: for deduplication)
  const removeResults = [];
  for (const rule of existingRules) {
    try {
      const res = await fetch('http://localhost:8000/delete_rule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rule_id: rule.rule_id, protocol_id })
      });

      if (res.ok) {
        removeResults.push({ success: true, rule: rule.rule_code });
      } else {
        const msg = await res.text();
        removeResults.push({ success: false, rule: rule.rule_code, error: msg });
      }
    } catch (err) {
      removeResults.push({ success: false, rule: rule.rule_code, error: (err as Error).message });
    }
  }

  // Add the new full block as a single rule
  const payload = {
    rule_id: `rule_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    protocol_id,
    sponsor,
    rule_code: newRuleCode,
    date_created: timestamp,
    date_amended: timestamp
  };

  const addResults = [];

  try {
    const res = await fetch('http://localhost:8000/add_rule', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      addResults.push({ success: true, rule: newRuleCode });
    } else {
      const msg = await res.text();
      addResults.push({ success: false, rule: newRuleCode, error: msg });
    }
  } catch (err) {
    addResults.push({ success: false, rule: newRuleCode, error: (err as Error).message });
  }

  const added = addResults.filter(r => r.success).map(r => r.rule);
  const failed = [...addResults, ...removeResults].filter(r => !r.success);

  return {
    success: failed.length === 0,
    message: `Added 1 rule block. Removed ${removeResults.length} old rule(s).`,
    added,
    removed: removeResults.map(r => r.rule),
    failed
  };
}


// Get the read_ddt_items so the autocomplete variables fill.
export function fetchAutocompleteItems() {
  const res = fetchDDTItems();
  return res;
}



// web socket stuff
let socket: WebSocket | null = null;
let listeners: ((message: any) => void)[] = [];
let connectionPromise: Promise<void> | null = null;
let reconnectTimeout: NodeJS.Timeout | null = null;

export function connectWebSocket(onMessage: (message: any) => void): Promise<void> {
  // Remove any existing instance of this listener first
  listeners = listeners.filter(l => l !== onMessage);
  
  // Add the listener
  listeners.push(onMessage);
  
  // If already connecting, return existing promise
  if (connectionPromise) {
    return connectionPromise;
  }
  
  // If already connected, return resolved promise
  if (socket && socket.readyState === WebSocket.OPEN) {
    return Promise.resolve();
  }
  
  // Create new connection promise
  connectionPromise = new Promise((resolve, reject) => {
    try {
      socket = new WebSocket('ws://localhost:8000/ws');
      
      socket.onopen = () => {
        console.log('WebSocket connection established');
        connectionPromise = null;
        if (reconnectTimeout) {
          clearTimeout(reconnectTimeout);
          reconnectTimeout = null;
        }
        resolve();
      };
      
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log(`[WebSocket] Dispatching message to ${listeners.length} listeners`);
          listeners.forEach((cb) => cb(data));
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      
      socket.onclose = () => {
        console.log('WebSocket connection closed');
        socket = null;
        connectionPromise = null;
        
        // Attempt to reconnect after 2 seconds
        if (!reconnectTimeout) {
          reconnectTimeout = setTimeout(() => {
            console.log('Attempting to reconnect WebSocket...');
            reconnectTimeout = null;
            // Re-establish connection for existing listeners
            if (listeners.length > 0) {
              connectWebSocket(listeners[0]);
            }
          }, 2000);
        }
      };
      
      socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        connectionPromise = null;
        reject(error);
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      connectionPromise = null;
      reject(error);
    }
  });
  
  return connectionPromise;
}

export function isWebSocketConnected(): boolean {
  return socket !== null && socket.readyState === WebSocket.OPEN;
}

export async function ensureWebSocketConnection(): Promise<void> {
  if (!isWebSocketConnected()) {
    // Need at least one listener for connection to work
    if (listeners.length === 0) {
      await connectWebSocket(() => {});
    } else {
      await connectWebSocket(listeners[0]);
    }
  }
}


export async function sendAuto(ruleText: string, system_prompt: string, rule_id: string) {
  const protocol_id = get(selectedStudy)?.name;
  if (!protocol_id) {
    console.error('No protocol selected');
    return;
  }

  // Ensure connection before sending
  await ensureWebSocketConnection();
  
  const isWorkflow = ruleText.trim().toUpperCase().includes("WORKFLOW:");

  if (socket && socket.readyState === WebSocket.OPEN) {
    if (isWorkflow) {
      socket.send(JSON.stringify({ dsl: ruleText, protocol_id }));
      console.log("Sent DSL workflow");
    } else {
      socket.send(JSON.stringify({ rule_code: ruleText, system_prompt, protocol_id, rule_id }));
      console.log("Sent single-shot rule");
    }
  } else {
    console.error('WebSocket is not connected after ensureWebSocketConnection');
  }
}


export async function sendChatMessage(rule_code: string, system_prompt: string, rule_id: string) { //nathan change
  const protocol_id = get(selectedStudy)?.name;
  
  // Ensure connection before sending
  await ensureWebSocketConnection();
  
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ rule_code, system_prompt, protocol_id, rule_id }));
    console.log('Sent rule + prompt:', { rule_code, system_prompt, protocol_id, rule_id });
  } else {
    console.error('WebSocket is not connected after ensureWebSocketConnection');
  }
}

export async function sendWorkflow(dsl: string) {
  const protocol_id = get(selectedStudy)?.name;
  
  // Ensure connection before sending
  await ensureWebSocketConnection();
  
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ dsl, protocol_id }));
    console.log('Sent DSL workflow:', { dsl: dsl.substring(0, 100) + '...', protocol_id });
  } else {
    console.error('WebSocket is not connected after ensureWebSocketConnection');
  }
}

export async function getCards(): Promise<Card[]> {
  const protocol_id = get(selectedStudy)?.name;
  try {
    const response = await fetch(`http://localhost:8000/get_cards?protocol_id=${protocol_id}`);
    if (!response.ok) throw new Error(`Error: ${response.statusText}`);
    return await response.json();
  } catch (error) {
    console.error('Error fetching cards:', error);
    throw error;
  }
}


export async function addCard(card: Card): Promise<void> {
  // Fill in seconds + timezone if missing
  function normalizeDate(datetimeLocal: string) {
    return new Date(datetimeLocal).toISOString(); // Adds full format with 'Z'
  }

  const formattedCard = {
    ...card,
    date_created: normalizeDate(card.date_created),
    date_amended: normalizeDate(card.date_amended)
  };

  const response = await fetch('http://localhost:8000/add_card', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(formattedCard)
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to add card');
  }
}

export async function deleteCard(sponsor: string, protocolId: string, prompt: string): Promise<void> {
  try {
    // Encode the prompt to handle special characters in the URL
    const encodedPrompt = encodeURIComponent(prompt);
    const response = await fetch(`http://localhost:8000/delete_card/${encodeURIComponent(sponsor)}/${encodeURIComponent(protocolId)}/${encodedPrompt}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Failed to delete card: ${response.status} ${response.statusText}`);
    }
  } catch (error) {
    console.error('Error deleting card:', error);
    throw error;
  }
}

export async function updateCard(updatedCard: Card): Promise<void> {
  try {
    const response = await fetch('http://localhost:8000/update_card', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updatedCard),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Failed to update card');
    }
  } catch (error) {
    console.error('Error updating card:', error);
    throw error;
  }
}

export async function saveDslFile(path: string, contents: string) {
  const res = await fetch('http://localhost:8000/save_dsl_file', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ path, contents }),
  });
  if (!res.ok) {
    throw new Error(`Failed to save DSL file: ${res.status} ${res.statusText}`);
  }
}