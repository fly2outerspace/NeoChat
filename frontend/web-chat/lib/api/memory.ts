/**
 * Memory API client
 */
import { getConfig } from '@/lib/config';

export interface CharacterMemoryItem {
  type: 'schedule' | 'scenario';
  start_at: string;
  end_at: string;
  content: string;
  title?: string | null;
  entry_id?: string | null;
  scenario_id?: string | null;
  session_id: string;
}

export interface CharacterMemoryResponse {
  character_id: string;
  character_name: string;
  items: CharacterMemoryItem[];
}

export interface MemoryResponse {
  characters: CharacterMemoryResponse[];
}

export interface CharacterRelationItem {
  relation_id: string;
  session_id: string;
  name: string;
  knowledge: string;
  progress: string;
  created_at?: string | null;
}

export interface CharacterRelationResponse {
  character_id: string;
  character_name: string;
  relations: CharacterRelationItem[];
}

export interface RelationResponse {
  characters: CharacterRelationResponse[];
}

/**
 * Get all memory data (schedules and scenarios) for all characters
 */
export async function getAllMemory(): Promise<MemoryResponse> {
  const config = getConfig();
  try {
    const response = await fetch(`${config.baseUrl}/v1/memory`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(config.apiKey && { Authorization: `Bearer ${config.apiKey}` }),
      },
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Failed to get memory: ${response.status} ${text}`);
    }

    // Check if response is JSON
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      const text = await response.text();
      throw new Error(
        `服务器返回了非JSON响应。请检查后端服务是否正常运行。响应类型: ${contentType}`
      );
    }

    return await response.json();
  } catch (error: any) {
    // Handle network errors (e.g., backend not running)
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      throw new Error(
        `无法连接到后端服务 (${config.baseUrl})。请确保后端服务正在运行。`
      );
    }
    throw error;
  }
}

/**
 * Get all relation data for all characters
 */
export async function getAllRelations(): Promise<RelationResponse> {
  const config = getConfig();
  try {
    const response = await fetch(`${config.baseUrl}/v1/relations`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(config.apiKey && { Authorization: `Bearer ${config.apiKey}` }),
      },
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Failed to get relations: ${response.status} ${text}`);
    }

    // Check if response is JSON
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      const text = await response.text();
      throw new Error(
        `服务器返回了非JSON响应。请检查后端服务是否正常运行。响应类型: ${contentType}`
      );
    }

    return await response.json();
  } catch (error: any) {
    // Handle network errors (e.g., backend not running)
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      throw new Error(
        `无法连接到后端服务 (${config.baseUrl})。请确保后端服务正在运行。`
      );
    }
    throw error;
  }
}

