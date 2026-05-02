export interface Profile {
  /**
   * Crockford base32 ULID, 26 chars.
   */
  id: string;
  /**
   * Crockford base32 ULID, 26 chars.
   */
  attendee_id: string;
  source: "github" | "linkedin" | "resume";
  fetched_at: string;
  /**
   * Source-specific raw payload.
   */
  data: {
    [k: string]: unknown;
  };
  facts: ProfileFacts;
}
/**
 * Flattened, comparable facts extracted from a Profile. Used by the comparison engine.
 */
export interface ProfileFacts {
  languages?: {
    name: string;
    evidence: "github" | "linkedin" | "resume";
    confidence?: number;
    loc?: number;
    first_seen_year?: number | null;
    [k: string]: unknown;
  }[];
  experience?: {
    company: string;
    title?: string | null;
    /**
     * YYYY-MM
     */
    start?: string | null;
    /**
     * YYYY-MM or null if current
     */
    end?: string | null;
    [k: string]: unknown;
  }[];
  education?: {
    school: string;
    degree?: string | null;
    field?: string | null;
    /**
     * YYYY
     */
    end?: string | null;
    [k: string]: unknown;
  }[];
  projects?: {
    name: string;
    url?: string | null;
    stars?: number | null;
    [k: string]: unknown;
  }[];
  credentials?: {
    name: string;
    issuer?: string | null;
    [k: string]: unknown;
  }[];
}
