import type { WsEnvelope } from '@/contracts/generated'

const _wsBase = import.meta.env.VITE_WS_BASE as string | undefined
if (!_wsBase) {
  if (!import.meta.env.DEV) {
    throw new Error('VITE_WS_BASE is not set. Copy .env.example to .env and set your Tailscale backend IP.')
  }
}
const WS_BASE = _wsBase ?? 'ws://localhost:8000'

type Handler = (data: unknown) => void

export class WSClient {
  private ws: WebSocket | null = null
  private backoff = 1000
  private readonly maxBackoff = 30_000
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private handlers = new Map<string, Set<Handler>>()
  private token = ''
  private shouldReconnect = false
  private sessionId: string | null = null

  connect(token: string): void {
    this.token = token
    this.shouldReconnect = true
    this._open()
  }

  disconnect(): void {
    this.shouldReconnect = false
    this._clearTimer()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this._emit('disconnected', null)
  }

  send(type: string, data: unknown, sessionId?: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return
    const envelope: WsEnvelope = {
      id: crypto.randomUUID(),
      type,
      ts: new Date().toISOString(),
      session_id: sessionId ?? this.sessionId,
      data: data as Record<string, unknown>,
    }
    this.ws.send(JSON.stringify(envelope))
  }

  setSessionId(id: string | null): void {
    this.sessionId = id
  }

  on(type: string, handler: Handler): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set())
    }
    this.handlers.get(type)!.add(handler)
    return () => {
      this.handlers.get(type)?.delete(handler)
    }
  }

  private _open(): void {
    this._emit('connecting', null)
    const url = `${WS_BASE}/ws/phone?token=${this.token}`
    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.backoff = 1000
      this._emit('connected', null)
    }

    this.ws.onmessage = (event: MessageEvent<string>) => {
      try {
        const envelope = JSON.parse(event.data) as WsEnvelope
        // Reset backoff on any successful message
        this.backoff = 1000
        this._emit(envelope.type, envelope.data)
      } catch {
        // ignore malformed frames
      }
    }

    this.ws.onclose = () => {
      this.ws = null
      if (this.shouldReconnect) {
        this._scheduleReconnect()
      } else {
        this._emit('disconnected', null)
      }
    }

    this.ws.onerror = () => {
      // onclose fires after onerror, so reconnect logic lives there
    }
  }

  private _scheduleReconnect(): void {
    const jitter = (Math.random() * 0.4 - 0.2) * this.backoff
    const delay = Math.min(this.backoff + jitter, this.maxBackoff)
    this._emit('reconnecting', { delay })
    this.reconnectTimer = setTimeout(() => {
      this._open()
    }, delay)
    this.backoff = Math.min(this.backoff * 2, this.maxBackoff)
  }

  private _clearTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  private _emit(type: string, data: unknown): void {
    const set = this.handlers.get(type)
    if (set) {
      set.forEach((h) => h(data))
    }
  }
}

export const wsClient = new WSClient()
