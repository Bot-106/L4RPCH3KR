export type Event = {
  id: string;
  name: string;
  starts_at: string;
  ends_at: string;
  consent_jurisdiction: string;
  retention_days: number;
  created_by_user_id: string;
  attendee_count?: number;
};

export type EventStats = {
  attendees: number;
  avg_score: number;
  flags: number;
  registered: number;
  latest_flag: { id: string; severity: string; created_at: string } | null;
};

export type Attendee = {
  id: string;
  event_id: string;
  firstname?: string;
  lastname?: string;
  full_name: string;
  email: string;
  socials?: { linkedin?: string | null; github?: string | null; instagram?: string | null; website?: string | null };
  headline: string | null;
  linkedin_url: string | null;
  github_login: string | null;
  resume_url: string | null;
  photo_url: string | null;
  profile_pic_url?: string | null;
  larp_score?: number | null;
  flag_count?: number;
  processing_status?: string;
  consented_to_recording: boolean;
  imported_at: string;
  deleted_at?: string | null;
};

export type Session = {
  id: string;
  event_id: string;
  self_user_id: string | null;
  wearer_id: string | null;
  partner_attendee_id: string | null;
  subject_id: string | null;
  partner_consent_status: string;
  started_at: string;
  ended_at: string | null;
  pi_device_id: string | null;
  device_id: string | null;
  score?: number | null;
  score_label?: string | null;
};

export type Utterance = {
  id: string;
  session_id: string;
  speaker: string;
  speaker_confidence: number;
  started_at: string;
  ended_at: string;
  text: string;
  transcript: string;
  audio_url?: string | null;
  audio_clip_url?: string | null;
};

export type Claim = {
  id: string;
  utterance_id: string;
  text?: string;
  claim_text?: string;
  type?: string;
  confidence?: number;
  [key: string]: unknown;
};

export type Flag = {
  id: string;
  session_id?: string;
  claim_id?: string;
  subject_id?: string;
  severity: "low" | "medium" | "high" | string;
  score_delta?: number;
  larp_score_delta?: number;
  claim_text?: string;
  verified_text?: string;
  explanation?: string;
  created_at?: string | null;
  [key: string]: unknown;
};

export type WsEnvelope<T = unknown> = {
  id: string;
  type: string;
  ts: string;
  session_id?: string | null;
  data: T;
};

export type ImportJob = {
  status: "running" | "succeeded" | "failed";
  rows_total: number;
  rows_done: number;
  errors: Array<{ row_number?: number; row?: unknown; message: string }>;
};

export type AttendeeSummary = {
  attendee: Attendee;
  github: {
    login?: string;
    name?: string;
    bio?: string;
    company?: string;
    location?: string;
    public_repos?: number;
    followers?: number;
    avatar_url?: string;
    html_url?: string;
    top_languages?: string[];
    recent_repos?: { name: string; description?: string | null; stars: number; url: string }[];
  };
  linkedin: {
    scraped?: boolean;
    name?: string | null;
    headline?: string | null;
    about?: string | null;
    location?: string | null;
    followers?: string | null;
    photoUrl?: string | null;
    experiences?: { title: string; company?: string | null; dates?: string | null }[];
    education?: { school: string; degree?: string | null }[];
    skills?: string[];
    url?: string | null;
    error?: string | null;
    title?: string | null;
    description?: string | null;
    image?: string | null;
  };
  comparison?: {
    linkedin_summary?: string;
    github_summary?: string;
    discrepancies?: string[];
    credibility?: "CONSISTENT" | "MINOR_GAPS" | "SIGNIFICANT_GAPS" | "UNKNOWN";
    credibility_reason?: string;
    larp_score?: number;
    larp_score_reason?: string;
    error?: string;
  };
  verified_profile: Record<string, unknown>;
  flags: Flag[];
  larp_score?: number | null;
  profile_larp_score?: number | null;
  profile_larp_label?: string | null;
};

export type LeaderboardEntry = {
  rank: number;
  attendee: Attendee;
  larp_score: number;
  flag_count: number;
};

export type EventFlag = Flag & {
  attendee?: Attendee | null;
  attendee_name?: string | null;
};

// NEXT_PUBLIC_API_BASE must be set at deploy time to point to the backend host.
// In local development (`npm run dev`) it falls back to http://localhost:8000.
// In production, omitting it means all API calls will silently target localhost —
// set NEXT_PUBLIC_API_BASE=http://100.76.124.67:8000 (or your Tailscale IP) in .env.local.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export function apiWsUrl(path: string) {
  const base = API_BASE.replace(/^http/, "ws").replace(/\/$/, "");
  return `${base}${path}`;
}

export function getToken() {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem("larpchekr_jwt") ?? "";
}

export function setToken(token: string) {
  window.localStorage.setItem("larpchekr_jwt", token);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers, cache: "no-store" });
  if (!res.ok) {
    const text = await res.text();
    let message: string | undefined;
    try {
      const parsed = JSON.parse(text) as { detail?: { error?: { message?: string } } | string };
      message = typeof parsed.detail === "string" ? parsed.detail : parsed.detail?.error?.message;
    } catch {
      message = undefined;
    }
    throw new Error(message ? `${res.status} ${message}` : `${res.status} ${text}`);
  }
  return (await res.json()) as T;
}

export const api = {
  signIn: (email: string) => request<{ jwt: string }>(`/auth/magic-link/callback?token=${encodeURIComponent(email)}`),
  events: () => request<{ events: Event[] }>("/events"),
  event: (eventId: string) => request<{ event: Event }>(`/events/${eventId}`),
  stats: (eventId: string) => request<EventStats>(`/events/${eventId}/stats`),
  createEvent: (name: string) => {
    const now = new Date();
    const ends = new Date(now.getTime() + 2 * 24 * 60 * 60 * 1000);
    return request<{ event: Event }>("/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, starts_at: now.toISOString(), ends_at: ends.toISOString(), consent_jurisdiction: "us-ca", retention_days: 30 })
    });
  },
  createSession: (eventId: string, deviceId = "browser-laptop") =>
    request<{ session: Session }>("/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_id: eventId, device_id: deviceId })
    }),
  attendees: (eventId: string) => request<{ attendees: Attendee[]; next_cursor: string | null }>(`/events/${eventId}/attendees`),
  leaderboard: (eventId?: string) => request<{ leaderboard: LeaderboardEntry[] }>(eventId ? `/leaderboard?event_id=${encodeURIComponent(eventId)}` : "/leaderboard"),
  flags: (eventId: string) => request<{ flags: EventFlag[] }>(`/events/${eventId}/flags`),
  createAttendee: (eventId: string, data: Partial<Attendee>) =>
    request<{ attendee: Attendee }>(`/events/${eventId}/attendees`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    }),
  importCsv: (eventId: string, file: File) => {
    const form = new FormData();
    form.set("csv", file);
    return request<{ import_job_id: string; estimated_seconds: number }>(`/events/${eventId}/attendees/import`, { method: "POST", body: form });
  },
  importJob: (eventId: string, jobId: string) => request<ImportJob>(`/events/${eventId}/attendees/import/${jobId}`),
  updateAttendee: (eventId: string, attendeeId: string, data: Partial<Attendee>) =>
    request<{ attendee: Attendee }>(`/events/${eventId}/attendees/${attendeeId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    }),
  fetchProfilePhoto: (eventId: string, attendeeId: string) => request<{ attendee: Attendee; profile_pic_url: string; source: string; has_embedding: boolean }>(`/events/${eventId}/attendees/${attendeeId}/profile-photo`, { method: "POST" }),
  attendeeSummary: (eventId: string, attendeeId: string) => request<AttendeeSummary>(`/events/${eventId}/attendees/${attendeeId}/summary`),
  deleteAttendee: (eventId: string, attendeeId: string) => request<{ attendee: Attendee }>(`/events/${eventId}/attendees/${attendeeId}`, { method: "DELETE" }),
  exportUrl: (eventId: string) => `${API_BASE}/events/${eventId}/export`
};
