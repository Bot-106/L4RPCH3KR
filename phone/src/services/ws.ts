import { WS_BASE } from '@env';
import type {
  WsEnvelope,
  PhoneHelloData,
  SubscribeSessionData,
  ConsumePairingQrData,
  SessionStatusData,
  PartnerIdentifiedData,
  TranscriptUpdateData,
  ClaimDetectedData,
  FlagRaisedData,
  ScoreUpdateData,
  PairingQrData,
  WsErrorData,
} from '@/contracts';

// Typed event map: backend → phone message types
export interface PhoneWsEvents {
  session_status: SessionStatusData;
  partner_identified: PartnerIdentifiedData;
  transcript_update: TranscriptUpdateData;
  claim_detected: ClaimDetectedData;
  flag_raised: FlagRaisedData;
  score_update: ScoreUpdateData;
  pairing_qr: PairingQrData;
  error: WsErrorData;
  _connected: undefined;
  _disconnected: { code: number; reason: string };
  _reconnecting: { attempt: number; delay: number };
}

type Listener<T> = (data: T) => void;
type AnyListener = (type: string, data: unknown) => void;

const APP_VERSION = '0.1.0';

const BACKOFF_BASE_MS = 1_000;
const BACKOFF_MAX_MS = 30_000;
const BACKOFF_JITTER = 0.2;

function backoffDelay(attempt: number): number {
  const exp = Math.min(BACKOFF_BASE_MS * 2 ** attempt, BACKOFF_MAX_MS);
  const jitter = exp * BACKOFF_JITTER * (Math.random() - 0.5);
  return Math.round(exp + jitter);
}

let msgSeq = 0;
function nextId(): string {
  return `ph-${Date.now()}-${++msgSeq}`;
}

export class PhoneWsClient {
  private ws: WebSocket | null = null;
  private jwt: string | null = null;
  private userId: string | null = null;
  private activeSessionId: string | null = null;

  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempt = 0;
  private shouldReconnect = false;
  private paused = false;

  private listeners: Map<string, Set<Listener<unknown>>> = new Map();
  private anyListeners: Set<AnyListener> = new Set();

  setCredentials(jwt: string, userId: string) {
    this.jwt = jwt;
    this.userId = userId;
  }

  connect() {
    if (!this.jwt || !this.userId) {
      console.warn('[WS] connect() called without credentials');
      return;
    }
    this.shouldReconnect = true;
    this.paused = false;
    this._openSocket();
  }

  disconnect() {
    this.shouldReconnect = false;
    this.activeSessionId = null;
    this._clearReconnectTimer();
    this.ws?.close(1000, 'user disconnect');
    this.ws = null;
  }

  pause() {
    // Called when the app backgrounds — iOS kills WS; we surface a paused state.
    this.paused = true;
    this.shouldReconnect = false;
    this.ws?.close(1000, 'app backgrounded');
    this.ws = null;
  }

  resume() {
    if (!this.paused) return;
    this.paused = false;
    this.shouldReconnect = true;
    this.reconnectAttempt = 0;
    this._openSocket();
  }

  subscribeSession(sessionId: string) {
    this.activeSessionId = sessionId;
    this._send<SubscribeSessionData>('subscribe_session', sessionId, {
      session_id: sessionId,
    });
  }

  unsubscribeSession(sessionId: string) {
    if (this.activeSessionId === sessionId) {
      this.activeSessionId = null;
    }
    this._send('unsubscribe_session', sessionId, { session_id: sessionId });
  }

  requestPairingQr() {
    this._send('request_pairing_qr', null, {});
  }

  consumePairingQr(token: string) {
    this._send<ConsumePairingQrData>('consume_pairing_qr', null, { token });
  }

  on<K extends keyof PhoneWsEvents>(
    type: K,
    listener: Listener<PhoneWsEvents[K]>,
  ): () => void {
    const key = type as string;
    if (!this.listeners.has(key)) {
      this.listeners.set(key, new Set());
    }
    this.listeners.get(key)!.add(listener as Listener<unknown>);
    return () => {
      this.listeners.get(key)?.delete(listener as Listener<unknown>);
    };
  }

  onAny(listener: AnyListener): () => void {
    this.anyListeners.add(listener);
    return () => this.anyListeners.delete(listener);
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  get isPaused(): boolean {
    return this.paused;
  }

  // ── Private ──────────────────────────────────────────────────────────────

  private _openSocket() {
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;
      this.ws.close();
    }

    const url = `${WS_BASE}/ws/phone?token=${encodeURIComponent(this.jwt!)}`;
    console.log(`[WS] connecting (attempt ${this.reconnectAttempt})`);
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log('[WS] connected');
      this.reconnectAttempt = 0;
      this._emit('_connected', undefined);
      this._send<PhoneHelloData>('phone_hello', null, {
        user_id: this.userId!,
        app_version: APP_VERSION,
      });
      if (this.activeSessionId) {
        this._send<SubscribeSessionData>('subscribe_session', this.activeSessionId, {
          session_id: this.activeSessionId,
        });
      }
    };

    this.ws.onmessage = (event) => {
      try {
        const envelope = JSON.parse(event.data as string) as WsEnvelope<unknown>;
        this._dispatch(envelope);
      } catch (e) {
        console.warn('[WS] malformed message', e);
      }
    };

    this.ws.onerror = (e) => {
      console.warn('[WS] error', e);
    };

    this.ws.onclose = (e) => {
      console.log(`[WS] closed code=${e.code} reason="${e.reason}"`);
      this._emit('_disconnected', { code: e.code, reason: e.reason });
      if (this.shouldReconnect && !this.paused) {
        this._scheduleReconnect();
      }
    };
  }

  private _scheduleReconnect() {
    this._clearReconnectTimer();
    const delay = backoffDelay(this.reconnectAttempt);
    console.log(`[WS] reconnecting in ${delay}ms (attempt ${this.reconnectAttempt + 1})`);
    this._emit('_reconnecting', { attempt: this.reconnectAttempt, delay });
    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempt += 1;
      this._openSocket();
    }, delay);
  }

  private _clearReconnectTimer() {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private _send<T>(type: string, sessionId: string | null, data: T) {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      console.warn(`[WS] tried to send "${type}" but socket is not open`);
      return;
    }
    const envelope: WsEnvelope<T> = {
      id: nextId(),
      type,
      ts: new Date().toISOString(),
      session_id: sessionId,
      data,
    };
    this.ws.send(JSON.stringify(envelope));
  }

  private _dispatch(envelope: WsEnvelope<unknown>) {
    const { type, data } = envelope;
    this._emit(type as keyof PhoneWsEvents, data);
    for (const listener of this.anyListeners) {
      listener(type, data);
    }
  }

  private _emit<K extends keyof PhoneWsEvents>(
    type: K,
    data: PhoneWsEvents[K],
  ) {
    const set = this.listeners.get(type as string) as Set<Listener<PhoneWsEvents[K]>> | undefined;
    if (!set) return;
    for (const listener of set) {
      try {
        listener(data);
      } catch (e) {
        console.error(`[WS] listener error for "${type as string}"`, e);
      }
    }
  }
}

// Singleton — one WS connection per app lifetime
export const wsClient = new PhoneWsClient();
