import { API_BASE } from '@env';
import type {
  User,
  Session,
  RecapResponse,
  Flag,
  PiPairResponse,
  VoiceCalibration,
  ApiError,
} from '@/contracts';

let _jwt: string | null = null;

export function setJwt(jwt: string | null) {
  _jwt = jwt;
}

class ApiRequestError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiRequestError';
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  headers?: Record<string, string>,
): Promise<T> {
  const baseHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...headers,
  };
  if (_jwt) {
    baseHeaders['Authorization'] = `Bearer ${_jwt}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: baseHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const errBody = (await res.json().catch(() => ({
      error: { code: 'unknown', message: res.statusText },
    }))) as ApiError;
    throw new ApiRequestError(
      res.status,
      errBody.error.code,
      errBody.error.message,
    );
  }

  return res.json() as Promise<T>;
}

async function multipartRequest<T>(
  path: string,
  formData: FormData,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (_jwt) {
    headers['Authorization'] = `Bearer ${_jwt}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!res.ok) {
    const errBody = (await res.json().catch(() => ({
      error: { code: 'unknown', message: res.statusText },
    }))) as ApiError;
    throw new ApiRequestError(
      res.status,
      errBody.error.code,
      errBody.error.message,
    );
  }

  return res.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export function requestMagicLink(email: string): Promise<{ ok: boolean }> {
  return request('POST', '/auth/magic-link', { email });
}

export function exchangeMagicLinkToken(
  token: string,
): Promise<{ user: User; jwt: string }> {
  return request('GET', `/auth/magic-link/callback?token=${encodeURIComponent(token)}`);
}

export function getGithubStartUrl(redirect: string): string {
  return `${API_BASE}/auth/github/start?redirect=${encodeURIComponent(redirect)}`;
}

// ── Users ─────────────────────────────────────────────────────────────────────

export function getMe(): Promise<{ user: User }> {
  return request('GET', '/users/me');
}

export function uploadVoiceCalibration(
  audioBlob: Blob,
): Promise<{ calibration: VoiceCalibration }> {
  const form = new FormData();
  form.append('audio', audioBlob, 'calibration.wav');
  return multipartRequest('/users/me/voice-calibration', form);
}

export function initPiPair(): Promise<PiPairResponse> {
  return request('POST', '/users/me/pi-pair', {});
}

// ── Partner pairing ───────────────────────────────────────────────────────────

export function createPairingToken(): Promise<{
  token: string;
  expires_at: string;
  qr_url: string;
}> {
  return request('POST', '/pairings', {});
}

export function consumePairingToken(
  token: string,
): Promise<{ session_id: string }> {
  return request('POST', '/pairings/consume', { token });
}

// ── Sessions ──────────────────────────────────────────────────────────────────

export function getSession(id: string): Promise<{ session: Session }> {
  return request('GET', `/sessions/${id}`);
}

export function getRecap(sessionId: string): Promise<RecapResponse> {
  return request('GET', `/sessions/${sessionId}/recap`);
}

export function createSession(eventId: string): Promise<{ session: Session }> {
  return request('POST', '/sessions', { event_id: eventId });
}

// ── Flags ─────────────────────────────────────────────────────────────────────

export function disputeFlag(
  flagId: string,
  reason: string,
): Promise<{ flag: Flag }> {
  return request('POST', `/flags/${flagId}/dispute`, { reason });
}

export { ApiRequestError };
