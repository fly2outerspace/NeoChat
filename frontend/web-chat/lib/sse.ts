/**
 * SSE (Server-Sent Events) Types
 * 
 * Unified event structure for streaming responses from the backend.
 * This simplified format replaces the verbose OpenAI format.
 */

/**
 * SSE Event types
 */
export type SSEEventType = 'token' | 'status' | 'done' | 'error';

/**
 * Tool information in SSE events
 */
export interface SSEToolInfo {
  /** Tool name (e.g., 'send_telegram_message', 'web_search') */
  name: string;
  /** Tool call ID for correlation */
  id: string;
}

/**
 * Unified SSE event structure
 * 
 * All streaming data payloads from the backend follow this structure.
 * 
 * @example Token event
 * { type: 'token', content: 'Hello' }
 * 
 * @example Token with tool info
 * { type: 'token', content: 'result', tool: { name: 'search', id: 'call_123' } }
 * 
 * @example Status event
 * { type: 'status', status: 'Thinking...', stage: 'strategy' }
 * 
 * @example Done event
 * { type: 'done' }
 * 
 * @example Error event
 * { type: 'error', content: 'Something went wrong' }
 */
export interface SSEEvent {
  /** Event type */
  type: SSEEventType;
  /** Text content (for token/error events) */
  content?: string;
  /** Status message (for status events) */
  status?: string;
  /** Tool information (when event is from a tool) */
  tool?: SSEToolInfo;
  /** Current execution stage (e.g., 'strategy', 'speak') */
  stage?: string;
  /** Flow node ID that generated this event */
  node_id?: string;
}

/**
 * Parse SSE data line to SSEEvent
 * 
 * @param data - Raw SSE data string (without 'data: ' prefix)
 * @returns Parsed SSEEvent or null if invalid
 */
export function parseSSEEvent(data: string): SSEEvent | null {
  if (!data || data === '[DONE]') {
    return null;
  }
  
  try {
    const event = JSON.parse(data) as SSEEvent;
    // Validate required field
    if (!event.type) {
      console.warn('SSE event missing type field:', data);
      return null;
    }
    return event;
  } catch (e) {
    console.error('Failed to parse SSE event:', data, e);
    return null;
  }
}

/**
 * Check if SSE event is a token event with content
 */
export function isTokenEvent(event: SSEEvent): event is SSEEvent & { content: string } {
  return event.type === 'token' && typeof event.content === 'string';
}

/**
 * Check if SSE event is a status event
 */
export function isStatusEvent(event: SSEEvent): event is SSEEvent & { status: string } {
  return event.type === 'status' && typeof event.status === 'string';
}

/**
 * Check if SSE event is a done event
 */
export function isDoneEvent(event: SSEEvent): boolean {
  return event.type === 'done';
}

/**
 * Check if SSE event is an error event
 */
export function isErrorEvent(event: SSEEvent): event is SSEEvent & { content: string } {
  return event.type === 'error';
}

/**
 * Check if event has tool information
 */
export function hasToolInfo(event: SSEEvent): event is SSEEvent & { tool: SSEToolInfo } {
  return event.tool !== undefined && event.tool !== null;
}

