export interface Event {
  /**
   * Crockford base32 ULID, 26 chars.
   */
  id: string;
  name: string;
  starts_at: string;
  ends_at: string;
  /**
   * ISO 3166-2 region code, e.g. us-ca, us-ny, eu-de
   */
  consent_jurisdiction: string;
  retention_days: number;
  /**
   * Crockford base32 ULID, 26 chars.
   */
  created_by_user_id: string;
}
