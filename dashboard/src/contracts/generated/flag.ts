export interface Flag {
  /**
   * Crockford base32 ULID, 26 chars.
   */
  id: string;
  /**
   * Crockford base32 ULID, 26 chars.
   */
  claim_id: string;
  /**
   * Crockford base32 ULID, 26 chars.
   */
  profile_id: string;
  severity: "low" | "medium" | "high";
  score_delta: number;
  verified_text: string;
  confidence: number;
  created_at: string;
  disputed: boolean;
  dispute_reason?: string | null;
}
