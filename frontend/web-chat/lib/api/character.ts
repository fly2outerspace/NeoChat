/**
 * Character API client
 */
import { getConfig } from '@/lib/config';

export interface Character {
  id: number;
  character_id: string;
  name: string;
  roleplay_prompt: string | null;
  avatar: string | null;
  created_at: string;
  updated_at: string;
}

export interface CharacterCreateRequest {
  name: string;
  roleplay_prompt?: string | null;
  avatar?: string | null;
  character_id?: string | null;
}

export interface CharacterUpdateRequest {
  name?: string | null;
  roleplay_prompt?: string | null;
  avatar?: string | null;
}

/**
 * List all characters
 */
export async function listCharacters(): Promise<Character[]> {
  const config = getConfig();
  try {
    const response = await fetch(`${config.baseUrl}/v1/characters`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(config.apiKey && { Authorization: `Bearer ${config.apiKey}` }),
      },
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Failed to list characters: ${response.status} ${text}`);
    }

    const data = await response.json();
    return data.characters || [];
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
 * Get a character by character_id
 */
export async function getCharacter(character_id: string): Promise<Character> {
  const config = getConfig();
  const response = await fetch(`${config.baseUrl}/v1/characters/${character_id}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(config.apiKey && { Authorization: `Bearer ${config.apiKey}` }),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to get character: ${response.status} ${text}`);
  }

  return await response.json();
}

/**
 * Create a new character
 */
export async function createCharacter(request: CharacterCreateRequest): Promise<Character> {
  const config = getConfig();
  const response = await fetch(`${config.baseUrl}/v1/characters`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(config.apiKey && { Authorization: `Bearer ${config.apiKey}` }),
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to create character: ${response.status} ${text}`);
  }

  return await response.json();
}

/**
 * Update a character
 */
export async function updateCharacter(
  character_id: string,
  request: CharacterUpdateRequest
): Promise<Character> {
  const config = getConfig();
  const response = await fetch(`${config.baseUrl}/v1/characters/${character_id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...(config.apiKey && { Authorization: `Bearer ${config.apiKey}` }),
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to update character: ${response.status} ${text}`);
  }

  return await response.json();
}

/**
 * Delete a character
 */
export async function deleteCharacter(character_id: string): Promise<void> {
  const config = getConfig();
  const response = await fetch(`${config.baseUrl}/v1/characters/${character_id}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      ...(config.apiKey && { Authorization: `Bearer ${config.apiKey}` }),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to delete character: ${response.status} ${text}`);
  }
}

