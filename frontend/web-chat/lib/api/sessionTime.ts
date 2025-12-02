import { getConfig } from '@/lib/config';

export type TimeActionType = 'scale' | 'offset' | 'freeze';

export interface TimeActionDto {
  type: TimeActionType;
  value: number;
  note?: string | null;
}

export interface SessionTimeResponse {
  session_id: string;
  base_virtual: string;
  base_real: string;
  actions: TimeActionDto[];
  current_virtual_time: string;
  current_real_time: string;
  updated_at?: string | null;
  real_updated_at?: string | null;
}

export interface UpdateSessionTimeRequest {
  base_virtual?: string;
  actions?: TimeActionDto[];
  reset_actions?: boolean;
  rebase?: boolean;
  // legacy fields for quick operations
  mode?: string;
  offset_seconds?: number;
  fixed_time?: string;
  speed?: number;
  virtual_start?: string;
}

async function requestSessionTime<T>(
  sessionId: string,
  path: string,
  options?: RequestInit
): Promise<T> {
  const config = getConfig();
  try {
    const response = await fetch(`${config.baseUrl}/v1/sessions/${sessionId}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(config.apiKey && { Authorization: `Bearer ${config.apiKey}` }),
      },
      ...options,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Session time API error (${response.status}): ${text}`);
    }

    return (await response.json()) as T;
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

export async function fetchSessionTime(sessionId: string): Promise<SessionTimeResponse> {
  return requestSessionTime<SessionTimeResponse>(sessionId, `/time`, {
    method: 'GET',
  });
}

export async function updateSessionTime(
  sessionId: string,
  payload: UpdateSessionTimeRequest
): Promise<SessionTimeResponse> {
  return requestSessionTime<SessionTimeResponse>(sessionId, `/time`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function seekSessionTime(
  sessionId: string,
  virtualTime: string
): Promise<SessionTimeResponse> {
  return requestSessionTime<SessionTimeResponse>(sessionId, `/time/seek`, {
    method: 'POST',
    body: JSON.stringify({ virtual_time: virtualTime }),
  });
}

export async function nudgeSessionTime(
  sessionId: string,
  deltaSeconds: number
): Promise<SessionTimeResponse> {
  return requestSessionTime<SessionTimeResponse>(sessionId, `/time/nudge`, {
    method: 'POST',
    body: JSON.stringify({ delta_seconds: deltaSeconds }),
  });
}

export async function setSessionTimeSpeed(
  sessionId: string,
  speed: number
): Promise<SessionTimeResponse> {
  return requestSessionTime<SessionTimeResponse>(sessionId, `/time/speed`, {
    method: 'POST',
    body: JSON.stringify({ speed }),
  });
}

