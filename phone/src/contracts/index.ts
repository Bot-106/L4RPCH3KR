// Hand-written types mirroring contracts/schemas/*.schema.json.
// Run `npm run contracts` to regenerate into src/contracts/generated/
// and update imports here to point at that directory.

export type Ulid = string;
export type IsoTimestamp = string;
export type Confidence = number; // [0, 1]
export type Severity = 'low' | 'medium' | 'high';
export type Hedge = 'none' | 'weak' | 'strong';
export type Speaker = 'self' | 'partner' | 'unknown';
export type ConsentStatus = 'pending' | 'granted' | 'denied';
export type ProfileSource = 'github' | 'linkedin' | 'resume';
export type SessionStatusValue = 'armed' | 'active' | 'ended';

export interface User {
  id: Ulid;
  email: string;
  display_name: string;
  created_at: IsoTimestamp;
  voice_calibration_id: Ulid | null;
  github_login: string | null;
}

export interface Attendee {
  id: Ulid;
  event_id: Ulid;
  user_id: Ulid | null;
  full_name: string;
  email: string;
  headline: string | null;
  linkedin_url: string | null;
  github_login: string | null;
  resume_url: string | null;
  photo_url: string | null;
  consented_to_recording: boolean;
  imported_at: IsoTimestamp;
  deleted_at: IsoTimestamp | null;
}

export interface Session {
  id: Ulid;
  event_id: Ulid;
  self_user_id: Ulid;
  partner_attendee_id: Ulid | null;
  partner_consent_status: ConsentStatus;
  started_at: IsoTimestamp;
  ended_at: IsoTimestamp | null;
  pi_device_id: string;
}

export interface Utterance {
  id: Ulid;
  session_id: Ulid;
  speaker: Speaker;
  speaker_confidence: Confidence;
  started_at: IsoTimestamp;
  ended_at: IsoTimestamp;
  text: string;
  audio_url: string | null;
}

export type ClaimKind =
  | 'language_experience'
  | 'employment'
  | 'education'
  | 'project'
  | 'credential'
  | 'quantitative';

export interface Claim {
  id: Ulid;
  utterance_id: Ulid;
  kind: ClaimKind;
  subject: string;
  predicate: string;
  value: Record<string, unknown>;
  hedge: Hedge;
  extraction_confidence: Confidence;
  text_span: string;
}

export interface Flag {
  id: Ulid;
  claim_id: Ulid;
  profile_id: Ulid;
  severity: Severity;
  score_delta: number;
  verified_text: string;
  confidence: Confidence;
  created_at: IsoTimestamp;
  disputed: boolean;
  dispute_reason: string | null;
}

export interface VoiceCalibration {
  id: Ulid;
  user_id: Ulid;
  sample_audio_url: string;
  created_at: IsoTimestamp;
}

// WS envelope
export interface WsEnvelope<T = unknown> {
  id: string;
  type: string;
  ts: IsoTimestamp;
  session_id: Ulid | null;
  data: T;
}

// Phone → backend payloads
export interface PhoneHelloData {
  user_id: Ulid;
  app_version: string;
}

export interface SubscribeSessionData {
  session_id: Ulid;
}

export interface ConsumePairingQrData {
  token: string;
}

// Backend → phone payloads
export interface SessionStatusData {
  session_id: Ulid;
  status: SessionStatusValue;
  partner: Attendee | null;
}

export interface PartnerIdentifiedData {
  session_id: Ulid;
  attendee: Attendee;
}

export interface TranscriptUpdateData {
  session_id: Ulid;
  utterances: Utterance[];
}

export interface ClaimDetectedData {
  session_id: Ulid;
  claim: Claim;
}

export interface FlagRaisedData {
  session_id: Ulid;
  flag: Flag;
  claim: Claim;
  utterance: Utterance;
}

export interface ScoreUpdateData {
  session_id: Ulid;
  score: Confidence;
}

export interface PairingQrData {
  token: string;
  expires_at: IsoTimestamp;
  qr_url: string;
}

export interface WsErrorData {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

// REST shapes
export interface RecapResponse {
  session: Session;
  partner: Attendee | null;
  utterances: Utterance[];
  claims: Claim[];
  flags: Flag[];
  score: number;
}

export interface PiPairResponse {
  pair_token: string;
  expires_at: IsoTimestamp;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
