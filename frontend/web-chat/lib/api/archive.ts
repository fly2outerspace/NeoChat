/**
 * Archive management API client
 */
import { getConfig } from '@/lib/config';

function getApiBaseUrl(): string {
  const config = getConfig();
  return config.baseUrl || 'http://localhost:8000';
}

export interface ArchiveInfo {
  name: string;
  path: string;
  size: number;
  created_at: string;
  modified_at: string;
}

export interface ArchiveListResponse {
  archives: ArchiveInfo[];
  current_archive: null; // Always null, frontend doesn't need to know about working database
}

export interface ArchiveResponse {
  success: boolean;
  message: string;
  archive: ArchiveInfo | null;
  imported_characters?: string[] | null; // List of character_id values newly imported from archive
}

export interface ArchiveCreateRequest {
  name: string;
}

export interface ArchiveSwitchRequest {
  name: string | null;
}

/**
 * List all available archives
 */
export async function listArchives(): Promise<ArchiveListResponse> {
  const response = await fetch(`${getApiBaseUrl()}/v1/archives`);
  if (!response.ok) {
    throw new Error(`Failed to list archives: ${response.statusText}`);
  }
  return response.json();
}


/**
 * Create a new archive
 */
export async function createArchive(name: string): Promise<ArchiveResponse> {
  const response = await fetch(`${getApiBaseUrl()}/v1/archives`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to create archive: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Delete an archive
 */
export async function deleteArchive(name: string): Promise<ArchiveResponse> {
  const response = await fetch(`${getApiBaseUrl()}/v1/archives/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to delete archive: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Overwrite an archive with current database content
 * This copies the current active database to the target archive location.
 * If the archive exists, it will be replaced. If it doesn't exist, it will be created.
 */
export async function overwriteArchive(name: string): Promise<ArchiveResponse> {
  const response = await fetch(`${getApiBaseUrl()}/v1/archives/overwrite`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    let errorMessage = `Failed to overwrite archive: ${response.statusText}`;
    try {
      const error = await response.json();
      errorMessage = error.detail || error.message || errorMessage;
    } catch (e) {
      // If response is not JSON, use status text
      errorMessage = `Failed to overwrite archive: ${response.status} ${response.statusText}`;
    }
    throw new Error(errorMessage);
  }
  return response.json();
}

/**
 * Load an archive into working database
 */
export async function loadArchive(name: string): Promise<ArchiveResponse> {
  const response = await fetch(`${getApiBaseUrl()}/v1/archives/load`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to load archive: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Create a new empty archive
 */
export async function createEmptyArchive(name: string): Promise<ArchiveResponse> {
  const response = await fetch(`${getApiBaseUrl()}/v1/archives/empty`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to create empty archive: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Create a new empty archive with auto-generated name (default_#) and switch to it
 */
export async function createEmptyArchiveAuto(): Promise<ArchiveResponse> {
  const response = await fetch(`${getApiBaseUrl()}/v1/archives/empty/auto`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to create empty archive auto: ${response.statusText}`);
  }
  return response.json();
}

