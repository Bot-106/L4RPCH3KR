export interface Session {
  /**
   * Crockford base32 ULID, 26 chars.
   */
  id: string;
  /**
   * Crockford base32 ULID, 26 chars.
   */
  event_id: string;
  /**
   * Crockford base32 ULID, 26 chars.
   */
  self_user_id: string;
  partner_attendee_id?: string | null;
  partner_consent_status: "pending" | "granted" | "denied";
  started_at: string;
  ended_at?: string | null;
  pi_device_id: string;
}
