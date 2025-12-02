/**
 * Frontend messages API client
 */
import { getConfig } from '@/lib/config';

export interface FrontendMessage {
  id: number;
  session_id: string;
  client_message_id: string;
  role: 'user' | 'assistant';
  message_kind: 'text' | 'tool_output' | 'user' | 'system';
  content: string;
  tool_name?: string;
  tool_call_id?: string;
  input_mode?: string;
  character_id?: string;
  display_order: number;
  created_at: string;
}

export interface FrontendMessageCreateRequest {
  session_id: string;
  client_message_id: string;
  role: 'user' | 'assistant';
  message_kind: 'text' | 'tool_output' | 'user' | 'system';
  content?: string;
  tool_name?: string;
  tool_call_id?: string;
  input_mode?: string;
  character_id?: string;
  display_order?: number;
  created_at?: string; // Virtual time when message was created
}

export interface FrontendMessageUpdateRequest {
  content?: string;
  tool_name?: string;
  created_at?: string;
}

function getApiBaseUrl(): string {
  const config = getConfig();
  return config.baseUrl || 'http://localhost:8000';
}

/**
 * Create a frontend message
 */
export async function createFrontendMessage(request: FrontendMessageCreateRequest): Promise<FrontendMessage> {
  const response = await fetch(`${getApiBaseUrl()}/v1/frontend-messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to create frontend message: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Get all frontend messages for a session
 */
export async function getFrontendMessages(sessionId: string): Promise<FrontendMessage[]> {
  const response = await fetch(`${getApiBaseUrl()}/v1/frontend-messages/${sessionId}`);
  if (!response.ok) {
    if (response.status === 404) {
      return [];
    }
    const error = await response.json();
    throw new Error(error.detail || `Failed to get frontend messages: ${response.statusText}`);
  }
  const data = await response.json();
  return data.messages || [];
}

/**
 * Delete all frontend messages for a session
 */
export async function deleteFrontendMessages(sessionId: string): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/v1/frontend-messages/${sessionId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to delete frontend messages: ${response.statusText}`);
  }
}

/**
 * Delete all frontend messages (used when switching archives)
 */
export async function deleteAllFrontendMessages(): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/v1/frontend-messages`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to delete all frontend messages: ${response.statusText}`);
  }
}

/**
 * Update an existing frontend message
 */
export async function updateFrontendMessage(messageId: number, request: FrontendMessageUpdateRequest): Promise<FrontendMessage> {
  const response = await fetch(`${getApiBaseUrl()}/v1/frontend-messages/${messageId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to update frontend message: ${response.statusText}`);
  }
  return response.json();
}

