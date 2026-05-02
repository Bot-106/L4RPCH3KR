// Hand-written from contracts/data-models.md and contracts/rest-api.md

export interface User {
  id: string
  email: string
  display_name: string
  created_at: string
  voice_calibration_id: string | null
  github_login: string | null
}

export interface Event {
  id: string
  name: string
  starts_at: string
  ends_at: string
  consent_jurisdiction: string
  retention_days: number
  created_by_user_id: string
}

export interface Attendee {
  id: string
  event_id: string
  user_id: string | null
  full_name: string
  email: string
  headline: string | null
  linkedin_url: string | null
  github_login: string | null
  resume_url: string | null
  photo_url: string | null
  consented_to_recording: boolean
  imported_at: string
}

export interface ProfileFacts {
  languages?: Array<{ name: string; evidence: string; confidence: number; loc?: number }>
  experience?: Array<{ company: string; title: string; start: string; end?: string }>
  education?: Array<{ school: string; degree: string; field: string; end?: string }>
  projects?: Array<{ name: string; stars?: number; url?: string }>
}

export interface Profile {
  id: string
  attendee_id: string
  source: 'github' | 'linkedin' | 'resume'
  fetched_at: string
  data: Record<string, unknown>
  facts: ProfileFacts
}

export type PartnerConsentStatus = 'pending' | 'granted' | 'denied'
export type SessionStatus = 'armed' | 'active' | 'ended'

export interface Session {
  id: string
  event_id: string
  self_user_id: string
  partner_attendee_id: string | null
  partner_consent_status: PartnerConsentStatus
  started_at: string
  ended_at: string | null
  pi_device_id: string
}

export type Speaker = 'self' | 'partner' | 'unknown'

export interface Utterance {
  id: string
  session_id: string
  speaker: Speaker
  speaker_confidence: number
  started_at: string
  ended_at: string
  text: string
  audio_url: string | null
}

export type ClaimKind =
  | 'language_experience'
  | 'employment'
  | 'education'
  | 'project'
  | 'credential'
  | 'quantitative'

export type HedgeLevel = 'none' | 'weak' | 'strong'

export interface Claim {
  id: string
  utterance_id: string
  kind: ClaimKind
  subject: string
  predicate: string
  value: Record<string, unknown>
  hedge: HedgeLevel
  extraction_confidence: number
  text_span: string
}

export type FlagSeverity = 'low' | 'medium' | 'high'

export interface Flag {
  id: string
  claim_id: string
  profile_id: string
  severity: FlagSeverity
  score_delta: number
  verified_text: string
  confidence: number
  created_at: string
  disputed: boolean
  dispute_reason: string | null
}

export interface VoiceCalibration {
  id: string
  user_id: string
  sample_audio_url: string
  created_at: string
}

export interface Pairing {
  token: string
  issuer_user_id: string
  expires_at: string
  consumed_by_user_id: string | null
  consumed_at: string | null
  qr_url?: string
}

// API response shapes

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

// WebSocket envelope and event types

export interface WsEnvelope<T = unknown> {
  id: string
  type: string
  ts: string
  session_id: string | null
  data: T
}

export interface WsSessionStatus {
  session_id: string
  status: SessionStatus
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
