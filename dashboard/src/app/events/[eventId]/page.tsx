"use client";

import { use, useEffect, useMemo, useState } from "react";
import { api, Attendee, Event, EventStats, getToken } from "@/lib/api";

export default function EventPage({ params }: { params: Promise<{ eventId: string }> }) {
  const { eventId } = use(params);
  const [event, setEvent] = useState<Event | null>(null);
  const [stats, setStats] = useState<EventStats | null>(null);
  const [attendees, setAttendees] = useState<Attendee[]>([]);
  const [sort, setSort] = useState<keyof Attendee>("full_name");
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [importErrors, setImportErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [photoLoading, setPhotoLoading] = useState<string | null>(null);
  const exportHref = `${api.exportUrl(eventId)}?token=${encodeURIComponent(getToken())}`;

  const sorted = useMemo(() => [...attendees].sort((a, b) => String(a[sort] ?? "").localeCompare(String(b[sort] ?? ""))), [attendees, sort]);

  function isHttpUrl(value: string | null | undefined) {
    return typeof value === "string" && /^https?:\/\//.test(value) && !value.includes("<");
  }

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const [eventRes, attendeeRes, statsRes] = await Promise.all([api.event(eventId), api.attendees(eventId), api.stats(eventId)]);
      setEvent(eventRes.event);
      setAttendees(attendeeRes.attendees);
      setStats(statsRes);
      setStatus(attendeeRes.attendees.length ? "" : "No attendees imported yet.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }

  async function upload(file: File | undefined) {
    if (!file) return;
    if (file.type && file.type !== "text/csv" && !file.name.endsWith(".csv")) {
      setError("Upload a CSV file.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("CSV must be <= 5 MB.");
      return;
    }
    setError(null);
    setImportErrors([]);
    setStatus("Importing...");
    try {
      const job = await api.importCsv(eventId, file);
      const poll = await api.importJob(eventId, job.import_job_id);
      setImportErrors(poll.errors.map((row) => `Row ${row.row_number ?? "?"}: ${row.message}`));
      const importStatus = `Import ${poll.status}: ${poll.rows_done}/${poll.rows_total} rows`;
      await load();
      setStatus(importStatus);
    } catch (err) {
      setStatus("");
      setError(err instanceof Error ? err.message : "Import failed");
    }
  }

  async function update(attendee: Attendee, field: keyof Attendee, value: string) {
    const previous = attendees;
    const optimistic = attendees.map((row) => (row.id === attendee.id ? { ...row, [field]: value } : row));
    setAttendees(optimistic);
    try {
      setError(null);
      const res = await api.updateAttendee(eventId, attendee.id, { [field]: value } as Partial<Attendee>);
      setAttendees((rows) => rows.map((row) => (row.id === attendee.id ? res.attendee : row)));
    } catch (err) {
      setAttendees(previous);
      setError(err instanceof Error ? err.message : "Update failed");
    }
  }

  async function remove(attendee: Attendee) {
    const previous = attendees;
    setAttendees(attendees.filter((row) => row.id !== attendee.id));
    setStatus(`Deleted ${attendee.full_name}. Refresh to undo before permanent cleanup.`);
    try {
      setError(null);
      await api.deleteAttendee(eventId, attendee.id);
      const statsRes = await api.stats(eventId);
      setStats(statsRes);
    } catch (err) {
      setAttendees(previous);
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function fetchPhoto(attendee: Attendee) {
    try {
      setError(null);
      setPhotoLoading(attendee.id);
      setStatus(`Fetching profile photo for ${attendee.full_name}...`);
      const res = await api.fetchProfilePhoto(eventId, attendee.id);
      setAttendees((rows) => rows.map((row) => (row.id === attendee.id ? res.attendee : row)));
      setStatus(`Fetched ${attendee.full_name}'s LinkedIn profile photo.`);
    } catch (err) {
      setStatus("");
      setError(err instanceof Error ? err.message : "Profile photo fetch failed");
    } finally {
      setPhotoLoading(null);
    }
  }

  useEffect(() => {
    if (!localStorage.getItem("larpchekr_jwt")) {
      window.location.href = "/sign-in";
      return;
    }
    void load();
  }, [eventId]);

  return (
    <main className="min-h-screen bg-[#f6f2e8] p-8 text-stone-950">
      <div className="mx-auto max-w-7xl">
        <div className="flex items-end justify-between gap-4">
          <div>
            <a className="text-sm font-bold text-orange-700" href="/events">Back to events</a>
            <h1 className="mt-2 text-4xl font-black">{event?.name ?? (loading ? "Loading event..." : "Event")}</h1>
            <p className="text-stone-600">{event?.attendee_count ?? attendees.length} attendees · dashboard core</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <a className="rounded-xl bg-orange-500 px-5 py-3 font-bold text-white" href={`/events/${eventId}/live`}>Laptop live check</a>
            <a className="rounded-xl bg-stone-950 px-5 py-3 font-bold text-white" href={exportHref}>Export CSV</a>
          </div>
        </div>

        <section className="mt-6 rounded-3xl border border-stone-300 bg-white p-5">
          <div className="flex flex-wrap items-center gap-4">
            <label className="rounded-xl border border-dashed border-stone-400 px-5 py-3 font-bold">
              Upload CSV
              <input className="hidden" type="file" accept=".csv,text/csv" onChange={(e) => void upload(e.target.files?.[0])} />
            </label>
            <p className="text-sm text-stone-600">Required columns: firstname,lastname. Optional: linkedin,github,instagram,website</p>
          </div>
          {status ? <p className="mt-4 rounded-xl bg-stone-100 p-3 text-sm">{status}</p> : null}
          {error ? <p className="mt-4 rounded-xl bg-red-100 p-3 text-sm text-red-800">{error}</p> : null}
          {importErrors.length ? (
            <div className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
              <p className="font-bold">Import warnings</p>
              {importErrors.map((message) => <p key={message}>{message}</p>)}
            </div>
          ) : null}
        </section>

        <section className="mt-6 grid grid-cols-5 gap-3">
          {[
            ["Attendees", stats?.attendees ?? attendees.length],
            ["Avg score", (stats?.avg_score ?? 0).toFixed(2)],
            ["Flags", stats?.flags ?? 0],
            ["Registered", stats?.registered ?? 0],
            ["Latest", stats?.latest_flag?.severity ?? "none"]
          ].map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-stone-300 bg-white p-4">
              <p className="text-xs font-bold uppercase tracking-widest text-stone-500">{label}</p>
              <p className="mt-2 text-2xl font-black">{value}</p>
            </div>
          ))}
        </section>

        <section className="mt-6 overflow-hidden rounded-3xl border border-stone-300 bg-white">
          <div className="grid grid-cols-[1.4fr_0.8fr_0.6fr_0.8fr_1fr_1fr_0.7fr] gap-3 border-b border-stone-200 bg-stone-950 px-4 py-3 text-sm font-bold text-white">
            <button className="text-left" onClick={() => setSort("full_name")}>Name</button>
            <span>Score</span>
            <span>Flags</span>
            <span>GitHub</span>
            <span>LinkedIn</span>
            <span>Status</span>
            <span />
          </div>
          {sorted.map((attendee) => (
            <div key={attendee.id} className="grid grid-cols-[1.4fr_0.8fr_0.6fr_0.8fr_1fr_1fr_0.7fr] gap-3 border-b border-stone-200 px-4 py-3 text-sm">
              <div className="flex items-center gap-3">
                {attendee.profile_pic_url || attendee.photo_url ? (
                  <button className="relative h-10 w-10 shrink-0 rounded-full border border-stone-200" title="Fetch/update profile photo" onClick={() => void fetchPhoto(attendee)} disabled={photoLoading === attendee.id}>
                    <img className="h-full w-full rounded-full object-cover" src={attendee.profile_pic_url ?? attendee.photo_url ?? ""} alt={`${attendee.full_name} profile`} />
                    {photoLoading === attendee.id ? <span className="absolute inset-0 flex items-center justify-center rounded-full bg-black/50 text-[10px] font-black text-white">...</span> : null}
                  </button>
                ) : (
                  <button className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-stone-200 text-xs font-black text-stone-600" title="Fetch profile photo" onClick={() => void fetchPhoto(attendee)} disabled={photoLoading === attendee.id}>{photoLoading === attendee.id ? "..." : "?"}</button>
                )}
                <input className="min-w-0 flex-1 rounded-lg border border-stone-200 px-2 py-1" defaultValue={attendee.full_name} onBlur={(e) => void update(attendee, "full_name", e.target.value)} />
              </div>
              <span className="rounded-lg bg-stone-100 px-2 py-1 font-bold">{attendee.larp_score == null ? "unavailable" : attendee.larp_score.toFixed(2)}</span>
              <span className="px-2 py-1">-</span>
              <input className="rounded-lg border border-stone-200 px-2 py-1" defaultValue={attendee.github_login ?? ""} onBlur={(e) => void update(attendee, "github_login", e.target.value)} />
              <div className="flex min-w-0 gap-2">
                <input className="min-w-0 flex-1 rounded-lg border border-stone-200 px-2 py-1" defaultValue={attendee.linkedin_url ?? ""} placeholder="LinkedIn URL or img snippet" onBlur={(e) => e.target.value !== (attendee.linkedin_url ?? "") ? void update(attendee, "linkedin_url", e.target.value) : undefined} />
                {isHttpUrl(attendee.linkedin_url) ? <a className="rounded-lg bg-blue-50 px-2 py-1 font-bold text-blue-700 underline" href={attendee.linkedin_url ?? ""} target="_blank" rel="noreferrer">Open</a> : null}
              </div>
              <span className="rounded-lg bg-emerald-50 px-2 py-1 font-bold text-emerald-800">{attendee.processing_status ?? "ready"}</span>
              <button className="rounded-lg bg-red-50 px-3 py-1 font-bold text-red-700" onClick={() => void remove(attendee)}>Delete</button>
            </div>
          ))}
          {!loading && sorted.length === 0 ? <p className="p-6 text-sm text-stone-600">No attendees yet. Upload a CSV to populate this event.</p> : null}
          {loading ? <p className="p-6 text-sm text-stone-600">Loading attendees...</p> : null}
        </section>
      </div>
    </main>
  );
}
