export interface Attendee {
  /**
   * Crockford base32 ULID, 26 chars.
   */
  id: string;
  /**
   * Crockford base32 ULID, 26 chars.
   */
  event_id: string;
  user_id?: string | null;
  full_name: string;
  email: string;
  headline?: string | null;
  linkedin_url?: string | null;
  github_login?: string | null;
  resume_url?: string | null;
  photo_url?: string | null;
  consented_to_recording: boolean;
  imported_at: string;
  deleted_at?: string | null;
}
