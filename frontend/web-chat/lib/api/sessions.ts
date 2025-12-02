/**
 * Sessions API client
 */
import { getConfig } from '@/lib/config';

export interface DatabaseSession {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface SessionListResponse {
  sessions: DatabaseSession[];
}

function getApiBaseUrl(): string {
  const config = getConfig();
  return config.baseUrl || 'http://localhost:8000';
}

/**
 * Get all sessions from the current database
 */
export async function getSessions(): Promise<DatabaseSession[]> {
  const response = await fetch(`${getApiBaseUrl()}/v1/sessions`);
  if (!response.ok) {
    if (response.status === 404) {
      return [];
    }
    const error = await response.json();
    throw new Error(error.detail || `Failed to get sessions: ${response.statusText}`);
  }
  const data: SessionListResponse = await response.json();
  return data.sessions || [];
}

