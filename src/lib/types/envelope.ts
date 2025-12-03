/**
 * Pattern Factory Message Protocol v1.1
 * TypeScript types matching Python envelope.py
 */

export type MessageType = 'request' | 'response' | 'error';
export type Verb = 'RULE' | 'CONTENT' | 'GENERIC';
export type Decision = 'yes' | 'no';

export interface MessageEnvelope {
  // Protocol metadata
  type: MessageType;
  version: string;
  timestamp: number;

  // Tracing
  session_id: string;
  request_id: string;

  // Message semantics
  verb: Verb;
  nextAgent: string | null;

  // Response metadata
  returnCode: number; // 0=continue, 1=success, negative=error
  decision: Decision | null;
  confidence: number; // 0.0-1.0
  reason: string;

  // Payload
  messageBody: Record<string, any>;
}

/**
 * Create a request message
 */
export function makeRequest(
  sessionId: string,
  requestId: string,
  verb: Verb,
  messageBody: Record<string, any>,
): MessageEnvelope {
  return {
    type: 'request',
    version: '1.1',
    timestamp: Date.now(),
    session_id: sessionId,
    request_id: requestId,
    verb,
    nextAgent: 'model.Capo',
    returnCode: 0,
    decision: null,
    confidence: 0.0,
    reason: '',
    messageBody,
  };
}

/**
 * Create a response message
 */
export function makeResponse(
  sessionId: string,
  requestId: string,
  verb: Verb,
  nextAgent: string | null,
  decision: Decision,
  confidence: number,
  reason: string,
  messageBody: Record<string, any>,
  returnCode: number = 0,
): MessageEnvelope {
  return {
    type: 'response',
    version: '1.1',
    timestamp: Date.now(),
    session_id: sessionId,
    request_id: requestId,
    verb,
    nextAgent,
    decision,
    confidence,
    reason,
    messageBody,
    returnCode,
  };
}

/**
 * Create an error message
 */
export function makeError(
  sessionId: string,
  requestId: string,
  verb: Verb,
  errorMessage: string,
): MessageEnvelope {
  return {
    type: 'error',
    version: '1.1',
    timestamp: Date.now(),
    session_id: sessionId,
    request_id: requestId,
    verb,
    nextAgent: null,
    returnCode: -1,
    decision: null,
    confidence: 0.0,
    reason: errorMessage,
    messageBody: {},
  };
}

/**
 * Create a success response
 */
export function makeSuccess(
  sessionId: string,
  requestId: string,
  verb: Verb,
  messageBody: Record<string, any>,
): MessageEnvelope {
  return {
    type: 'response',
    version: '1.1',
    timestamp: Date.now(),
    session_id: sessionId,
    request_id: requestId,
    verb,
    nextAgent: null,
    decision: 'yes',
    confidence: 1.0,
    reason: 'Success',
    messageBody,
    returnCode: 1,
  };
}

/**
 * Parse an incoming message and validate it's a valid envelope
 */
export function parseEnvelope(data: unknown): MessageEnvelope | null {
  if (typeof data !== 'object' || data === null) {
    return null;
  }

  const envelope = data as Record<string, any>;

  // Minimal validation
  if (!envelope.type || !envelope.verb || !envelope.session_id || !envelope.request_id) {
    return null;
  }

  return envelope as MessageEnvelope;
}
