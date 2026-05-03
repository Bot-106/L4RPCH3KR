"use client";

import { use, useEffect, useMemo, useRef, useState } from "react";
import { api, apiWsUrl, Attendee, AttendeeSummary, Event, EventStats, Flag, getToken, WsEnvelope } from "@/lib/api";
import { useAdmin } from "@/app/footer";

export default function EventPage({ params }: { params: Promise<{ eventId: string }> }) {
  const { isAdmin } = useAdmin();
  const { eventId } = use(params);
  const [event, setEvent] = useState<Event | null>(null);
  const [stats, setStats] = useState<EventStats | null>(null);
  const [attendees, setAttendees] = useState<Attendee[]>([]);
  const [ownedAttendeeIds, setOwnedAttendeeIds] = useState<Set<string>>(new Set());
  const [sort, setSort] = useState<keyof Attendee>("full_name");
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [importErrors, setImportErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [photoLoading, setPhotoLoading] = useState<string | null>(null);
  const [selectedAttendee, setSelectedAttendee] = useState<Attendee | null>(null);
  const [summary, setSummary] = useState<AttendeeSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState({ full_name: "", email: "", github_login: "", linkedin_url: "", headline: "" });
  const [exportHref, setExportHref] = useState(`${api.exportUrl(eventId)}?token=`);

  const sorted = useMemo(() => [...attendees].sort((a, b) => String(a[sort] ?? "").localeCompare(String(b[sort] ?? ""))), [attendees, sort]);

  function canEditAttendee(attendeeId: string): boolean {
    return isAdmin || ownedAttendeeIds.has(attendeeId);
  }

  function getLinkedInUsername(url: string | null | undefined): string {
    if (!url) return "";
    try {
      const urlObj = new URL(url);
      const pathname = urlObj.pathname.toLowerCase();
      // Extract username from URLs like: linkedin.com/in/username or linkedin.com/company/name
      const match = pathname.match(/\/(in|company)\/([^/?]+)/);
      return match ? match[2].replace(/[/-]/g, " ") : url;
    } catch {
      return url;
    }
  }

  function isHttpUrl(value: string | null | undefined) {
    return typeof value === "string" && /^https?:\/\//.test(value) && !value.includes("<");
  }

  function larpometer(score: number | null | undefined) {
    if (score == null || Number.isNaN(score)) return null;
    return Math.round(Math.min(1, Math.max(0, score)) * 100);
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

  async function createUser() {
    if (!createForm.full_name.trim()) {
      setError("Name is required.");
      return;
    }
    try {
      setCreating(true);
      setError(null);
      const res = await api.createAttendee(eventId, {
        full_name: createForm.full_name.trim(),
        email: createForm.email.trim(),
        github_login: createForm.github_login.trim(),
        linkedin_url: createForm.linkedin_url.trim(),
        headline: createForm.headline.trim(),
      });
      setAttendees((rows) => [res.attendee, ...rows]);
      setOwnedAttendeeIds((ids) => new Set([...ids, res.attendee.id]));
      setCreateForm({ full_name: "", email: "", github_login: "", linkedin_url: "", headline: "" });
      setCreateOpen(false);
      setStatus(`Created ${res.attendee.full_name}.`);
      const statsRes = await api.stats(eventId);
      setStats(statsRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create user failed");
    } finally {
      setCreating(false);
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

  async function openSummary(attendee: Attendee, refresh = false) {
    setSelectedAttendee(attendee);
    if (refresh) setStatus(`Refreshing ${attendee.full_name}'s profile...`);
    if (!refresh) setSummary(null);
    setSummaryLoading(true);
    try {
      const res = await api.attendeeSummary(eventId, attendee.id, refresh);
      // ── DEBUG: log everything the backend returned ──────────────────────────
      console.group(`[LARPCHEKR] Profile summary for ${attendee.full_name}`);
      console.log("Full response:", res);
      console.log("GitHub data:", res.github);
      console.log("LinkedIn data:", res.linkedin);
      console.log("Comparison:", res.comparison);
      console.log("Flags:", res.flags);
      console.log("Verified profile:", res.verified_profile);
      console.groupEnd();
      setSummary(res);
      setSelectedAttendee(res.attendee);
      setAttendees((rows) => rows.map((row) => (row.id === attendee.id ? res.attendee : row)));
      setStatus(res.cached ? `Loaded cached profile for ${attendee.full_name}.` : `Refreshed profile for ${attendee.full_name}.`);
    } catch (err) {
      console.error("[LARPCHEKR] summary fetch failed:", err);
      setSummary(null);
    } finally {
      setSummaryLoading(false);
    }
  }

  const selectedAttendeeRef = useRef<Attendee | null>(null);
  useEffect(() => { selectedAttendeeRef.current = selectedAttendee; }, [selectedAttendee]);

  useEffect(() => {
    const token = getToken();
    setExportHref(`${api.exportUrl(eventId)}?token=${encodeURIComponent(token)}`);
    if (!token) {
      window.location.href = "/sign-in";
      return;
    }
    void load();

    // Real-time phone WS: auto-update attendee larp scores and refresh
    // the open side-panel when a flag or score_update arrives for that attendee.
    const ws = new WebSocket(apiWsUrl("/ws/phone"));
    ws.onopen = () => {
      ws.send(JSON.stringify({ id: crypto.randomUUID(), type: "subscribe_global", ts: new Date().toISOString(), session_id: null, data: {} }));
    };
    ws.onmessage = (msg) => {
      const env = JSON.parse(msg.data as string) as WsEnvelope<Record<string, unknown>>;
      if (env.type === "session_available" && env.data.session_id) {
        const sid = String(env.data.session_id);
        ws.send(JSON.stringify({ id: crypto.randomUUID(), type: "subscribe_session", ts: new Date().toISOString(), session_id: sid, data: { session_id: sid } }));
      } else if (env.type === "score_update" && typeof env.data.score === "number" && env.data.subject_id) {
        const subjectId = String(env.data.subject_id);
        const newScore = Number(env.data.score);
        const newLabel = typeof env.data.label === "string" ? env.data.label : undefined;
        setAttendees((rows) => rows.map((a) => a.id === subjectId ? { ...a, larp_score: newScore } : a));
        if (selectedAttendeeRef.current?.id === subjectId) {
          setSummary((s) => s ? {
            ...s,
            larp_score: Math.max(newScore, s.larp_score ?? 0),
            profile_larp_label: newLabel ?? s.profile_larp_label,
            attendee: { ...s.attendee, larp_score: newScore },
          } : s);
        }
      } else if (env.type === "flag_raised" && env.data.flag) {
        const flag = env.data.flag as Flag;
        const subjectId = flag.subject_id;
        if (subjectId && selectedAttendeeRef.current?.id === subjectId) {
          setSummary((s) => s ? { ...s, flags: [flag, ...(s.flags ?? [])].slice(0, 50) } : s);
        }
      }
    };
    return () => ws.close();
  }, [eventId]);

  return (
    <main className="arcade-page">
      <header className="arcade-masthead">
        <div>
          <div className="arcade-wordmark">LarpChecker</div>
          <p className="mt-2 text-xs text-stone-400">ORGANIZER DASHBOARD · LIVE CREDENTIAL CHECK</p>
        </div>
        <nav className="flex flex-wrap gap-3 text-[10px]">
          <a className="px-3 py-2" href="/events">EVENTS</a>
          <a className="px-3 py-2" href={`/leaderboard?event_id=${encodeURIComponent(eventId)}`}>LARPERBOARD</a>
          <a className="px-3 py-2" href={`/events/${eventId}/flags`}>FLAGS</a>
          <a className="px-3 py-2" href={exportHref}>EXPORT</a>
          <a className="px-3 py-2" href="/settings">SETTINGS</a>
        </nav>
      </header>
      <div className="pixel-strip" />
      <div className="mx-auto max-w-7xl p-8">
        <div className="flex items-end justify-between gap-4">
          <div>
            <a className="text-sm font-bold text-orange-700" href="/events">Back to events</a>
            <h1 className="mt-2 text-4xl font-black">{event?.name ?? (loading ? "Loading event..." : "Event")}</h1>
            <p className="text-stone-600">{event?.attendee_count ?? attendees.length} attendees · dashboard core</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <a className="rounded-xl bg-stone-950 px-5 py-3 font-bold text-white" href={exportHref}>Export CSV</a>
          </div>
        </div>

        <section className="mt-6 rounded-3xl border border-stone-300 bg-white p-5">
          <div className="flex flex-wrap items-center gap-4">
            {isAdmin ? (
              <>
                <label className="rounded-xl bg-stone-950 px-5 py-3 font-bold text-white cursor-pointer hover:bg-stone-900">
                  Import CSV
                  <input type="file" accept=".csv" onChange={(e) => void upload(e.currentTarget.files?.[0])} className="hidden" />
                </label>
              </>
            ) : (
              <p className="rounded-xl border border-dashed border-stone-400 px-5 py-3 font-bold text-stone-600">CSV import disabled - Contact organizer if you are a hackathon organizer</p>
            )}
            <button
              className="rounded-xl bg-stone-950 px-5 py-3 font-bold text-white"
              onClick={() => setCreateOpen((open) => !open)}
              type="button"
            >
              {createOpen ? "Cancel" : "Create user"}
            </button>
            <p className="text-sm text-stone-600">Required columns: firstname,lastname. Optional: linkedin,github,instagram,website</p>
          </div>
          {createOpen ? (
            <div className="mt-4 rounded-2xl border border-stone-200 bg-stone-50 p-4">
              <div className="grid gap-3 md:grid-cols-2">
                <input
                  className="rounded-xl border border-stone-300 px-3 py-2"
                  placeholder="Full name"
                  value={createForm.full_name}
                  onChange={(e) => setCreateForm((form) => ({ ...form, full_name: e.target.value }))}
                />
                <input
                  className="rounded-xl border border-stone-300 px-3 py-2"
                  placeholder="Email"
                  type="email"
                  value={createForm.email}
                  onChange={(e) => setCreateForm((form) => ({ ...form, email: e.target.value }))}
                />
                <input
                  className="rounded-xl border border-stone-300 px-3 py-2"
                  placeholder="GitHub username"
                  value={createForm.github_login}
                  onChange={(e) => setCreateForm((form) => ({ ...form, github_login: e.target.value }))}
                />
                <input
                  className="rounded-xl border border-stone-300 px-3 py-2"
                  placeholder="LinkedIn URL"
                  value={createForm.linkedin_url}
                  onChange={(e) => setCreateForm((form) => ({ ...form, linkedin_url: e.target.value }))}
                />
                <input
                  className="rounded-xl border border-stone-300 px-3 py-2 md:col-span-2"
                  placeholder="Headline"
                  value={createForm.headline}
                  onChange={(e) => setCreateForm((form) => ({ ...form, headline: e.target.value }))}
                />
              </div>
              <div className="mt-3 flex justify-end">
                <button
                  className="rounded-xl bg-orange-600 px-5 py-2 font-bold text-white disabled:opacity-50"
                  disabled={creating}
                  onClick={() => void createUser()}
                  type="button"
                >
                  {creating ? "Creating..." : "Create user"}
                </button>
              </div>
            </div>
          ) : null}
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
          <div className={`grid ${isAdmin ? "grid-cols-[1.4fr_0.8fr_0.6fr_0.8fr_1fr_0.4fr]" : "grid-cols-[1.4fr_0.8fr_0.6fr_0.8fr_1fr]"} gap-3 border-b border-stone-200 bg-stone-950 px-4 py-3 text-sm font-bold text-white`}>
            <button className="text-left" onClick={() => setSort("full_name")}>Name</button>
            <span>Larpometer™</span>
            <span>Flags</span>
            <span>GitHub</span>
            <span>LinkedIn</span>
            {isAdmin && <span>Action</span>}
          </div>
          {sorted.map((attendee) => (
            <div key={attendee.id} className={`grid ${isAdmin ? "grid-cols-[1.4fr_0.8fr_0.6fr_0.8fr_1fr_0.4fr]" : "grid-cols-[1.4fr_0.8fr_0.6fr_0.8fr_1fr]"} gap-3 border-b border-stone-200 px-4 py-3 text-sm`}>
              <div className="flex items-center gap-3">
                {attendee.profile_pic_url || attendee.photo_url ? (
                  <button className="relative h-10 w-10 shrink-0 rounded-full border border-stone-200" title="Fetch/update profile photo" onClick={() => void fetchPhoto(attendee)} disabled={photoLoading === attendee.id}>
                    <img className="h-full w-full rounded-full object-cover" src={attendee.profile_pic_url ?? attendee.photo_url ?? ""} alt={`${attendee.full_name} profile`} />
                    {photoLoading === attendee.id ? <span className="absolute inset-0 flex items-center justify-center rounded-full bg-black/50 text-[10px] font-black text-white">...</span> : null}
                  </button>
                ) : (
                  <button className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-stone-200 text-xs font-black text-stone-600" title="Fetch profile photo" onClick={() => void fetchPhoto(attendee)} disabled={photoLoading === attendee.id}>{photoLoading === attendee.id ? "..." : "?"}</button>
                )}
                <button className="min-w-0 flex-1 truncate rounded-lg px-2 py-1 text-left font-semibold text-orange-700 underline-offset-2 hover:underline" onClick={() => void openSummary(attendee)}>{attendee.full_name}</button>
              </div>
              <span className="rounded-lg bg-stone-100 px-2 py-1 font-bold">{larpometer(attendee.larp_score) == null ? "unavailable" : larpometer(attendee.larp_score)}</span>
              <span className="px-2 py-1 font-bold">{attendee.flag_count ?? 0}</span>
              {canEditAttendee(attendee.id) ? (
                <input className="rounded-lg border border-stone-200 px-2 py-1" defaultValue={attendee.github_login ?? ""} onBlur={(e) => void update(attendee, "github_login", e.target.value)} />
              ) : attendee.github_login ? (
                <a href={`https://github.com/${attendee.github_login}`} target="_blank" rel="noreferrer" className="px-2 py-1 text-blue-600 hover:underline font-semibold">
                  {attendee.github_login}
                </a>
              ) : (
                <span className="px-2 py-1 text-stone-600">—</span>
              )}
              <div className="flex min-w-0 items-center justify-end gap-2">
                {canEditAttendee(attendee.id) ? (
                  <input className="min-w-0 w-full max-w-[240px] rounded-lg border border-stone-200 px-2 py-1 text-right" defaultValue={attendee.linkedin_url ?? ""} placeholder="LinkedIn URL or img snippet" onBlur={(e) => e.target.value !== (attendee.linkedin_url ?? "") ? void update(attendee, "linkedin_url", e.target.value) : undefined} />
                ) : isHttpUrl(attendee.linkedin_url) ? (
                  <a href={attendee.linkedin_url ?? ""} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline font-semibold">
                    {getLinkedInUsername(attendee.linkedin_url)}
                  </a>
                ) : (
                  <span className="text-right text-stone-600">—</span>
                )}
              </div>
              {isAdmin && (
                <div className="flex items-center justify-center">
                  <button
                    className="rounded-lg bg-red-100 px-2 py-1 text-xs font-bold text-red-700 hover:bg-red-200"
                    onClick={() => void remove(attendee)}
                    title="Delete attendee"
                  >
                    Delete
                  </button>
                </div>
              )}
            </div>
          ))}
          {!loading && sorted.length === 0 ? <p className="p-6 text-sm text-stone-600">No attendees yet. Upload a CSV to populate this event.</p> : null}
          {loading ? <p className="p-6 text-sm text-stone-600">Loading attendees...</p> : null}
        </section>
      </div>

      {/* Attendee summary side panel */}
      {selectedAttendee ? (
        <div className="fixed inset-0 z-50 flex justify-end" onClick={() => setSelectedAttendee(null)}>
          <div className="w-full max-w-md overflow-y-auto bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 flex items-center justify-between border-b border-stone-200 bg-white px-6 py-4">
              <div className="flex items-center gap-3">
                {(summary?.attendee.profile_pic_url ?? summary?.attendee.photo_url ?? summary?.github.avatar_url) ? (
                  <img
                    className="h-12 w-12 rounded-full object-cover ring-2 ring-stone-200"
                    src={summary?.attendee.profile_pic_url ?? summary?.attendee.photo_url ?? summary?.github.avatar_url ?? ""}
                    alt={selectedAttendee.full_name}
                  />
                ) : (
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-orange-100 text-lg font-black text-orange-700">
                    {selectedAttendee.full_name.charAt(0).toUpperCase()}
                  </div>
                )}
                <div>
                  <h2 className="text-lg font-black">{selectedAttendee.full_name}</h2>
                  <p className="text-sm text-stone-500">{selectedAttendee.headline ?? summary?.github.bio ?? ""}</p>
                </div>
              </div>
              <button className="rounded-lg p-2 text-stone-400 hover:bg-stone-100 hover:text-stone-700" onClick={() => setSelectedAttendee(null)}>✕</button>
            </div>

            {summaryLoading ? (
              <div className="flex flex-col items-center justify-center gap-3 py-20 text-stone-400">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-stone-200 border-t-orange-500" />
                <p className="text-sm">Fetching profile data...</p>
              </div>
            ) : summary ? (
              <div className="space-y-6 p-6">

                {/* Larp score */}
                <div className="flex items-center gap-3 rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3">
                  <span className="text-2xl">🎭</span>
                  <div>
                    <p className="text-xs font-bold uppercase tracking-widest text-stone-500">Larpometer™</p>
                    <p className="text-xl font-black">{larpometer(summary.larp_score) != null ? larpometer(summary.larp_score) : "No data"}</p>
                    {summary.profile_larp_label ? <p className="text-xs text-stone-500">{summary.profile_larp_label}</p> : null}
                  </div>
                  {summary.flags.length > 0 && (
                    <span className="ml-auto rounded-full bg-red-100 px-3 py-1 text-sm font-bold text-red-700">{summary.flags.length} flag{summary.flags.length !== 1 ? "s" : ""}</span>
                  )}
                </div>

                {/* ── AI Comparison card ──────────────────────────────── */}
                {summary.comparison && !summary.comparison.error && (
                  <div>
                    <h3 className="mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">Profile Verification</h3>
                    <div className={`rounded-2xl border p-4 space-y-3 ${
                      summary.comparison.credibility === "SIGNIFICANT_GAPS"
                        ? "border-red-200 bg-red-50"
                        : summary.comparison.credibility === "MINOR_GAPS"
                        ? "border-amber-200 bg-amber-50"
                        : "border-emerald-200 bg-emerald-50"
                    }`}>
                      {/* Credibility badge */}
                      <div className="flex items-center gap-2">
                        <span className={`rounded-full px-3 py-1 text-xs font-black uppercase tracking-wide ${
                          summary.comparison.credibility === "SIGNIFICANT_GAPS"
                            ? "bg-red-100 text-red-700"
                            : summary.comparison.credibility === "MINOR_GAPS"
                            ? "bg-amber-100 text-amber-700"
                            : "bg-emerald-100 text-emerald-700"
                        }`}>
                          {summary.comparison.credibility === "SIGNIFICANT_GAPS" ? "⚠ Significant Gaps"
                            : summary.comparison.credibility === "MINOR_GAPS" ? "△ Minor Gaps"
                            : summary.comparison.credibility === "CONSISTENT" ? "✓ Consistent"
                            : "? Unknown"}
                        </span>
                        {summary.comparison.credibility_reason && (
                          <p className="text-xs text-stone-600 italic">{summary.comparison.credibility_reason}</p>
                        )}
                      </div>

                      {summary.comparison.larp_score != null && (
                        <div className="rounded-xl bg-white/70 px-3 py-2">
                          <p className="text-xs font-bold text-stone-600">Haiku Larpometer™</p>
                          <p className="text-lg font-black text-stone-950">{larpometer(summary.comparison.larp_score) ?? 0}</p>
                          {summary.comparison.larp_score_reason && <p className="text-xs text-stone-600">{summary.comparison.larp_score_reason}</p>}
                        </div>
                      )}

                      {/* LinkedIn summary */}
                      {summary.comparison.linkedin_summary && (
                        <div>
                          <p className="text-xs font-bold text-blue-700 mb-1">LinkedIn claims</p>
                          <p className="text-sm text-stone-800">{summary.comparison.linkedin_summary}</p>
                        </div>
                      )}

                      {/* GitHub summary */}
                      {summary.comparison.github_summary && (
                        <div>
                          <p className="text-xs font-bold text-stone-600 mb-1">GitHub evidence</p>
                          <p className="text-sm text-stone-800">{summary.comparison.github_summary}</p>
                        </div>
                      )}

                      {/* Discrepancies */}
                      {summary.comparison.discrepancies && summary.comparison.discrepancies.length > 0 && (
                        <div>
                          <p className="text-xs font-bold text-red-700 mb-1.5">Discrepancies found</p>
                          <ul className="space-y-1">
                            {summary.comparison.discrepancies.map((d, i) => (
                              <li key={i} className="flex items-start gap-1.5 text-sm text-red-900">
                                <span className="mt-0.5 shrink-0 text-red-400">•</span>
                                {d}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {summary.comparison.discrepancies?.length === 0 && (
                        <p className="text-sm text-emerald-700">No discrepancies detected between LinkedIn and GitHub.</p>
                      )}
                    </div>
                  </div>
                )}

                {/* LinkedIn section — scraped via real Chrome session */}
                {selectedAttendee.linkedin_url ? (
                  <div>
                    <h3 className="mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">LinkedIn</h3>
                    {summary.linkedin.scraped ? (
                      <div className="arcade-panel border-2 border-black bg-white p-4 space-y-4 shadow-[6px_6px_0_#b9b9b9]">
                        <div className="flex items-start gap-3 border-b-2 border-black pb-3">
                          {(summary.linkedin.photoUrl ?? summary.linkedin.image) && (
                            <img className="h-14 w-14 border-2 border-black object-cover shrink-0" src={summary.linkedin.photoUrl ?? summary.linkedin.image ?? ""} alt="LinkedIn" />
                          )}
                          <div className="min-w-0 flex-1">
                            <p className="font-black text-black">{summary.linkedin.name ?? selectedAttendee.full_name}</p>
                            {summary.linkedin.headline && <p className="mt-1 text-sm text-stone-700">{summary.linkedin.headline}</p>}
                            {summary.linkedin.location && <p className="mt-1 text-xs text-stone-600">{summary.linkedin.location}</p>}
                          </div>
                        </div>
                        {summary.linkedin.about && (
                          <div>
                            <p className="mb-1 text-xs font-black uppercase text-stone-600">About</p>
                            <p className="border-l-4 border-black bg-stone-100 px-3 py-2 text-sm text-stone-900 line-clamp-5">{summary.linkedin.about}</p>
                          </div>
                        )}
                        {summary.linkedin.experiences && summary.linkedin.experiences.length > 0 && (
                          <div>
                            <p className="mb-1.5 text-xs font-black uppercase text-stone-600">Experience</p>
                            <div className="space-y-1.5">
                              {summary.linkedin.experiences.map((exp, i) => (
                                <div key={i} className="border-2 border-black bg-stone-50 px-3 py-2 text-sm shadow-[3px_3px_0_#d4d4d4]">
                                  <p className="font-bold text-black">{exp.title || "Experience"}</p>
                                  {exp.company && <p className="text-stone-700">{exp.company}</p>}
                                  {exp.dates && <p className="text-xs text-stone-500">{exp.dates}</p>}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {summary.linkedin.education && summary.linkedin.education.length > 0 && (
                          <div>
                            <p className="mb-1.5 text-xs font-black uppercase text-stone-600">Education</p>
                            <div className="space-y-1">
                              {summary.linkedin.education.map((edu, i) => (
                                <div key={i} className="border-2 border-black bg-stone-50 px-3 py-2 text-sm shadow-[3px_3px_0_#d4d4d4]">
                                  <p className="font-bold text-black">{edu.school || "Education"}</p>
                                  {edu.degree && <p className="text-stone-700">{edu.degree}</p>}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {summary.linkedin.skills && summary.linkedin.skills.length > 0 && (
                          <div>
                            <p className="mb-1.5 text-xs font-black uppercase text-stone-600">Skills</p>
                            <div className="flex flex-wrap gap-1.5">
                              {summary.linkedin.skills.map((s) => (
                                <span key={s} className="border-2 border-black bg-stone-100 px-2.5 py-1 text-xs font-bold text-black">{s}</span>
                              ))}
                            </div>
                          </div>
                        )}
                        {isHttpUrl(selectedAttendee.linkedin_url) && (
                          <a className="inline-block rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-bold text-white" href={selectedAttendee.linkedin_url} target="_blank" rel="noreferrer">Open LinkedIn →</a>
                        )}
                      </div>
                    ) : (
                      <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4 text-sm text-stone-500">
                        Could not scrape LinkedIn (Chrome may not be logged in, or playwright not installed).{" "}
                        {isHttpUrl(selectedAttendee.linkedin_url) && (
                          <a className="font-bold text-blue-600 underline" href={selectedAttendee.linkedin_url} target="_blank" rel="noreferrer">Open manually →</a>
                        )}
                      </div>
                    )}
                  </div>
                ) : null}

                {/* GitHub section */}
                {summary.github.login ? (
                  <div>
                    <h3 className="mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">GitHub</h3>
                    <div className="arcade-panel border-2 border-black bg-white p-4 shadow-[6px_6px_0_#b9b9b9]">
                      <div className="flex items-start justify-between gap-3 border-b-2 border-black pb-3">
                        <div>
                          <p className="font-black text-black">{summary.github.name ?? summary.github.login}</p>
                          {summary.github.bio && <p className="mt-1 text-sm text-stone-700">{summary.github.bio}</p>}
                          {summary.github.company && <p className="mt-1 text-sm text-stone-600">{summary.github.company}</p>}
                          {summary.github.location && <p className="text-sm text-stone-600">{summary.github.location}</p>}
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-1 text-sm">
                          <span className="font-black text-black">{summary.github.public_repos ?? 0} repos</span>
                          <span className="text-stone-600">{summary.github.followers ?? 0} followers</span>
                        </div>
                      </div>

                      {summary.github.top_languages && summary.github.top_languages.length > 0 && (
                        <div className="mt-3">
                          <p className="mb-1.5 text-xs font-bold text-stone-500">Top languages</p>
                          <div className="flex flex-wrap gap-1.5">
                            {summary.github.top_languages.map((lang) => (
                              <span key={lang} className="border-2 border-black bg-stone-100 px-2.5 py-1 text-xs font-bold text-black">{lang}</span>
                            ))}
                          </div>
                        </div>
                      )}

                      {summary.github.orgs && summary.github.orgs.length > 0 && (
                        <div className="mt-3">
                          <p className="mb-1.5 text-xs font-bold text-stone-500">Public orgs</p>
                          <div className="flex flex-wrap gap-1.5">
                            {summary.github.orgs.map((org) => (
                              org.url ? (
                                <a key={org.login ?? org.url} href={org.url} target="_blank" rel="noreferrer" className="plain-link border-2 border-black bg-white px-2.5 py-1 text-xs font-bold text-black shadow-[2px_2px_0_#d4d4d4] hover:bg-stone-50">{org.login}</a>
                              ) : (
                                <span key={org.login ?? "org"} className="border-2 border-black bg-white px-2.5 py-1 text-xs font-bold text-black">{org.login}</span>
                              )
                            ))}
                          </div>
                        </div>
                      )}

                      {summary.github.recent_repos && summary.github.recent_repos.length > 0 && (
                        <div className="mt-3">
                          <p className="mb-1.5 text-xs font-bold text-stone-500">Recent repos</p>
                          <div className="space-y-1.5">
                            {summary.github.recent_repos.map((repo) => (
                              <a key={repo.name} href={repo.url} target="_blank" rel="noreferrer" className="plain-link flex items-center justify-between gap-3 border-2 border-black bg-stone-50 px-3 py-2 text-sm text-black shadow-[3px_3px_0_#d4d4d4] hover:bg-white">
                                <span className="min-w-0 truncate font-bold text-black">{repo.name}</span>
                                <span className="shrink-0 font-bold text-stone-700">stars {repo.stars}</span>
                              </a>
                            ))}
                          </div>
                        </div>
                      )}

                      {summary.github.shared_repos && summary.github.shared_repos.length > 0 && (
                        <div className="mt-3">
                          <p className="mb-1.5 text-xs font-bold text-stone-500">Shared / org repos</p>
                          <div className="space-y-1.5">
                            {summary.github.shared_repos.map((repo) => (
                              <a key={repo.full_name ?? repo.name} href={repo.url} target="_blank" rel="noreferrer" className="plain-link flex items-center justify-between gap-3 border-2 border-black bg-stone-50 px-3 py-2 text-sm text-black shadow-[3px_3px_0_#d4d4d4] hover:bg-white">
                                <span className="min-w-0 truncate font-bold text-black">{repo.full_name ?? repo.name}</span>
                                <span className="shrink-0 font-bold text-stone-700">stars {repo.stars}</span>
                              </a>
                            ))}
                          </div>
                        </div>
                      )}

                      {summary.github.html_url && (
                        <a className="mt-3 inline-block rounded-lg bg-stone-900 px-3 py-1.5 text-sm font-bold text-white" href={summary.github.html_url} target="_blank" rel="noreferrer">View GitHub →</a>
                      )}
                    </div>
                  </div>
                ) : null}

                {/* Live observations (dot-jots from Pi audio) */}
                {summary.dot_jots && summary.dot_jots.length > 0 && (
                  <div>
                    <h3 className="mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">
                      What they said · live observations
                    </h3>
                    <div className="rounded-2xl border border-violet-200 bg-violet-50 p-4">
                      <ul className="space-y-1.5">
                        {summary.dot_jots.map((note, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm">
                            <span className="mt-0.5 shrink-0 font-bold text-violet-400">·</span>
                            <span className="text-violet-900">{note}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}

                {/* Flags */}
                {summary.flags.length > 0 && (
                  <div>
                    <h3 className="mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">Recent Flags</h3>
                    <div className="space-y-2">
                      {summary.flags.slice(0, 5).map((flag) => (
                        <div key={flag.id} className={`rounded-xl border p-3 text-sm ${flag.severity === "high" ? "border-red-200 bg-red-50" : flag.severity === "medium" ? "border-amber-200 bg-amber-50" : "border-stone-200 bg-stone-50"}`}>
                          <div className="flex items-center gap-2">
                            <span className={`rounded-full px-2 py-0.5 text-xs font-bold uppercase ${flag.severity === "high" ? "bg-red-100 text-red-700" : flag.severity === "medium" ? "bg-amber-100 text-amber-700" : "bg-stone-200 text-stone-600"}`}>{flag.severity}</span>
                            <span className="text-stone-600">{flag.verified_text ?? flag.explanation ?? "Claim mismatch detected"}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* No data fallback */}
                {!summary.github.login && !summary.linkedin.title && summary.flags.length === 0 && (
                  <div className="rounded-2xl border border-dashed border-stone-300 p-6 text-center text-stone-400">
                    <p className="text-2xl">🔍</p>
                    <p className="mt-2 text-sm">No profile data found. Add a GitHub login or LinkedIn URL to enrich this attendee.</p>
                  </div>
                )}

                <div className="border-t-2 border-black pt-4">
                  <div className="mb-2 text-xs text-stone-600">
                    {summary.cached ? "Loaded from cached profile summary." : "Fresh profile summary saved to database."}
                    {summary.profile_summary_cached_at ? ` Cached at ${new Date(summary.profile_summary_cached_at).toLocaleString()}.` : ""}
                  </div>
                  <button
                    type="button"
                    className="px-4 py-2 text-xs font-bold"
                    disabled={summaryLoading || !selectedAttendee}
                    onClick={() => selectedAttendee ? void openSummary(selectedAttendee, true) : undefined}
                  >
                    {summaryLoading ? "Refreshing..." : "Refresh profile check"}
                  </button>
                </div>
              </div>
            ) : (
              <div className="p-6 text-center text-sm text-stone-400">Failed to load profile data.</div>
            )}
          </div>
        </div>
      ) : null}
    </main>
  );
}
