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
  processing_status?: string;
  consented_to_recording: boolean;
  imported_at: string;
  deleted_at?: string | null;
};

export type ImportJob = {
  status: "running" | "succeeded" | "failed";
  rows_total: number;
  rows_done: number;
  errors: Array<{ row?: unknown; message: string }>;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

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
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
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
  attendees: (eventId: string) => request<{ attendees: Attendee[]; next_cursor: string | null }>(`/events/${eventId}/attendees`),
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
  deleteAttendee: (eventId: string, attendeeId: string) => request<{ attendee: Attendee }>(`/events/${eventId}/attendees/${attendeeId}`, { method: "DELETE" }),
  exportUrl: (eventId: string) => `${API_BASE}/events/${eventId}/export`
};
