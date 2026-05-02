// UI-only types and API response shapes.
// Entity types (User, Attendee, Session, etc.) are generated from JSON Schemas —
// import them from '@/contracts/generated' instead.

import type {
  User,
  Attendee,
  Session,
  Utterance,
  Claim,
  Flag,
  VoiceCalibration,
} from '@/contracts/generated'

export type { VoiceCalibration }

// ─── API response shapes ─────────────────────────���────────────────────────────
// These are phone-specific wrappers around entity types and are NOT in the JSON
// schemas; they must stay here.

export interface MagicLinkResponse {
  ok: boolean
}

export interface AuthCallbackResponse {
  user: User
  jwt: string
}

export interface VoiceCalibrationResponse {
  calibration: VoiceCalibration
}

export interface PiPairResponse {
  pair_token: string
  expires_at: string
}

export interface PairingCreateResponse {
  token: string
  expires_at: string
  qr_url: string
}

export interface PairingConsumeResponse {
  session_id: string
}

export interface SessionResponse {
  session: Session
}

export interface RecapResponse {
  session: Session
  partner: Attendee | null
  utterances: Utterance[]
  claims: Claim[]
  flags: Flag[]
  score: number
}

export interface FlagDisputeResponse {
  flag: Flag
}

// ─── WebSocket payload types (backend → phone) ───────────────────────────��───
// These wrap entity types into the per-event `data` payloads.
// They are phone-specific and are NOT top-level JSON schemas.

export interface WsSessionStatus {
  session_id: string
  status: 'armed' | 'active' | 'ended'
  partner: Attendee | null
}

export interface WsPartnerIdentified {
  session_id: string
  attendee: Attendee
}

export interface WsTranscriptUpdate {
  session_id: string
  utterances: Utterance[]
}

export interface WsClaimDetected {
  session_id: string
  claim: Claim
}

export interface WsFlagRaised {
  session_id: string
  flag: Flag
  claim: Claim
  utterance: Utterance
}

export interface WsScoreUpdate {
  session_id: string
  score: number
}

export interface WsPairingQr {
  token: string
  expires_at: string
  qr_url: string
}

export interface WsError {
  code: string
  message: string
}
