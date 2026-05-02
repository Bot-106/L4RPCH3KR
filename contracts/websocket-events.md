# Websocket events

Two WS endpoints, one envelope shape, three directions.

## Endpoints

- `wss://api.larpchekr.app/ws/pi` — Pi clients. Auth: `?token=<pi_pairing_token>`.
- `wss://api.larpchekr.app/ws/phone` — phone clients. Auth: `?token=<user_jwt>`.

Phones never connect to the Pi endpoint and vice versa.

## Envelope

Every JSON message:

```json
{
  "id": "01HX...",          // client-generated unique id, used for ack
  "type": "audio_chunk",    // see tables below
  "ts": "2026-05-01T12:34:56.789Z",
  "session_id": "01HX...",  // required once a session is active
  "data": { ... }           // type-specific payload
}
```

Schema: `schemas/ws-envelope.schema.json`. Per-type payload schemas in `schemas/ws-events.schema.json`.

Binary frames (audio PCM) skip the envelope and are sent as raw `bytes`. The most recent `audio_meta` JSON message scopes them.

## Pi → backend

| Type | Trigger | Payload |
|------|---------|---------|
| `pi_hello` | first message after WS connect | `{ device_id, firmware_version, battery_pct }` |
| `session_start` | user starts a session via phone (Pi is told via backend) — Pi acks | `{ session_id }` |
| `audio_meta` | before each burst of audio binary frames | `{ sample_rate: 16000, encoding: "pcm_s16le", channels: 1, frame_ms: 250, speaker_hint?: "self" }` |
| `(binary)` | continuous during VAD-positive speech | raw PCM bytes, scoped by last `audio_meta` |
| `frame_snapshot` | every 10s during a session, or on demand | `{ image_b64, width, height }` (base64 JPEG, ≤640×480) |
| `session_end` | session ended on Pi (manual button) | `{ session_id, reason }` |
| `heartbeat` | every 10s | `{ battery_pct, cpu_temp_c, buffer_seconds }` |
| `buffer_drain_start` / `buffer_drain_end` | bracketing post-outage replay | `{ session_id, buffered_seconds }` |

## Backend → Pi

| Type | Trigger | Payload |
|------|---------|---------|
| `haptic_pulse` | a flag was raised | `{ severity: "low" | "medium" | "high", pattern: [ms_on, ms_off, ...] }` |
| `recording_indicator` | partner consent state changes | `{ state: "off" | "armed" | "recording" }` — drives Pi LED |
| `session_ack` | confirms `session_start` | `{ session_id }` |
| `error` | client did something wrong | `{ code, message }` |

## Phone → backend

| Type | Trigger | Payload |
|------|---------|---------|
| `phone_hello` | first message after WS connect | `{ user_id, app_version }` |
| `subscribe_session` | user enters live mode | `{ session_id }` |
| `unsubscribe_session` | user leaves live mode | `{ session_id }` |
| `request_pairing_qr` | user taps "show QR" | `{}` — backend responds with `pairing_qr` |
| `consume_pairing_qr` | user scanned partner's QR | `{ token }` |

## Backend → phone

| Type | Trigger | Payload |
|------|---------|---------|
| `session_status` | session lifecycle change | `{ session_id, status: "armed" | "active" | "ended", partner: Attendee? }` |
| `partner_identified` | partner resolved post-pairing | `{ session_id, attendee: Attendee }` |
| `transcript_update` | new utterance(s) finalized — debounced 500ms | `{ session_id, utterances: Utterance[] }` |
| `claim_detected` | claim extracted (with or without flag) | `{ session_id, claim: Claim }` |
| `flag_raised` | discrepancy found | `{ session_id, flag: Flag, claim: Claim, utterance: Utterance }` |
| `score_update` | larp score recomputed | `{ session_id, score: float }` |
| `pairing_qr` | response to `request_pairing_qr` | `{ token, expires_at, qr_url }` |
| `error` | client did something wrong | `{ code, message }` |

## Ordering and reliability

- Within a session, the backend guarantees in-order delivery of `transcript_update`, `claim_detected`, and `flag_raised` for events from the same utterance.
- The Pi's audio binary frames have no ordering guarantee inside a 1-second window — the backend reorders by frame timestamp embedded in the binary header (first 8 bytes: int64 ms since epoch). Spec in `schemas/audio-frame-header.md` (TBD).
- WS reconnect: clients re-send `pi_hello` / `phone_hello` and re-`subscribe_session`. The backend replays missed events with a `since` cursor (TBD — for v1, just resync from `GET /sessions/:id/recap`).

## Error codes

`error.code` enum:
- `auth_invalid`
- `session_not_found`
- `session_already_started`
- `pairing_token_expired`
- `pairing_token_consumed`
- `unsupported_event_type`
- `rate_limited`
- `internal_error`

## Open questions

- Should `flag_raised` be acked by the phone before haptic fires, to ensure the user sees the card synchronized with the buzz? Probably no — haptic is independent and faster matters more. But test in user-testing.
- Should `audio_chunk` ever go to the phone for live caption display? Out of scope for v1; transcripts come via `transcript_update` only.
