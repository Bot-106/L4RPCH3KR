export interface Utterance {
  /**
   * Crockford base32 ULID, 26 chars.
   */
  id: string;
  /**
   * Crockford base32 ULID, 26 chars.
   */
  session_id: string;
  speaker: "self" | "partner" | "unknown";
  speaker_confidence: number;
  started_at: string;
  ended_at: string;
  text: string;
  audio_url?: string | null;
}
