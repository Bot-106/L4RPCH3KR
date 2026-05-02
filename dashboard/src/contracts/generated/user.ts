export interface User {
  /**
   * Crockford base32 ULID, 26 chars.
   */
  id: string;
  email: string;
  display_name: string;
  created_at: string;
  voice_calibration_id?: string | null;
  github_login?: string | null;
}
