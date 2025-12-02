/**
 * Model API client
 */
import { getConfig } from '@/lib/config';

export interface Model {
  id: number;
  model_id: string;
  name: string;
  provider: string;
  model: string;
  base_url: string;
  api_key: string | null;
  has_api_key?: boolean;
  max_tokens: number;
  temperature: number;
  api_type: string;
  created_at: string;
  updated_at: string;
}

export interface ModelCreateRequest {
  name: string;
  provider: string;
  model: string;
  base_url: string;
  api_key?: string | null;
  max_tokens?: number;
  temperature?: number;
  api_type?: string;
  model_id?: string | null;
}

export interface ModelUpdateRequest {
  name?: string | null;
  provider?: string | null;
  model?: string | null;
  base_url?: string | null;
  api_key?: string | null;
  max_tokens?: number | null;
  temperature?: number | null;
  api_type?: string | null;
}

/**
 * List all models
 */
export async function listModels(): Promise<Model[]> {
  const config = getConfig();
  const response = await fetch(`${config.baseUrl}/v1/models`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(config.apiKey && { Authorization: `Bearer ${config.apiKey}` }),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to list models: ${response.status} ${text}`);
  }

  const data = await response.json();
  return data.models || [];
}

/**
 * Get a model by model_id
 */
export async function getModel(model_id: string, include_api_key: boolean = false): Promise<Model> {
  const config = getConfig();
  const response = await fetch(`${config.baseUrl}/v1/models/${model_id}?include_api_key=${include_api_key}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(config.apiKey && { Authorization: `Bearer ${config.apiKey}` }),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to get model: ${response.status} ${text}`);
  }

  return await response.json();
}

/**
 * Create a new model
 */
export async function createModel(request: ModelCreateRequest): Promise<Model> {
  const config = getConfig();
  const response = await fetch(`${config.baseUrl}/v1/models`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(config.apiKey && { Authorization: `Bearer ${config.apiKey}` }),
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to create model: ${response.status} ${text}`);
  }

  return await response.json();
}

/**
 * Update a model
 */
export async function updateModel(
  model_id: string,
  request: ModelUpdateRequest
): Promise<Model> {
  const config = getConfig();
  const response = await fetch(`${config.baseUrl}/v1/models/${model_id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...(config.apiKey && { Authorization: `Bearer ${config.apiKey}` }),
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to update model: ${response.status} ${text}`);
  }

  return await response.json();
}

/**
 * Delete a model
 */
export async function deleteModel(model_id: string): Promise<void> {
  const config = getConfig();
  const response = await fetch(`${config.baseUrl}/v1/models/${model_id}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      ...(config.apiKey && { Authorization: `Bearer ${config.apiKey}` }),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to delete model: ${response.status} ${text}`);
  }
}

