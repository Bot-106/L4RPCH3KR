"use client";

import { use, useEffect, useMemo, useState } from "react";
import { api, Attendee, AttendeeSummary, Event, EventStats, getToken } from "@/lib/api";

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
  const [selectedAttendee, setSelectedAttendee] = useState<Attendee | null>(null);
  const [summary, setSummary] = useState<AttendeeSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState({ full_name: "", email: "", github_login: "", linkedin_url: "", headline: "" });
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

  async function openSummary(attendee: Attendee) {
    setSelectedAttendee(attendee);
    setSummary(null);
    setSummaryLoading(true);
    try {
      const res = await api.attendeeSummary(eventId, attendee.id);
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
    } catch (err) {
      console.error("[LARPCHEKR] summary fetch failed:", err);
      setSummary(null);
    } finally {
      setSummaryLoading(false);
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
    <main className="arcade-page">
      <header className="arcade-masthead">
        <div>
          <div className="arcade-wordmark">LarpChecker</div>
          <p className="mt-2 text-xs text-stone-400">ORGANIZER DASHBOARD · LIVE CREDENTIAL CHECK</p>
        </div>
        <nav className="flex flex-wrap gap-3 text-[10px]">
          <a className="px-3 py-2" href="/events">EVENTS</a>
          <a className="px-3 py-2" href={`/events/${eventId}/live`}>LIVE</a>
          <a className="px-3 py-2" href={exportHref}>EXPORT</a>
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
                <button className="min-w-0 flex-1 truncate rounded-lg px-2 py-1 text-left font-semibold text-orange-700 underline-offset-2 hover:underline" onClick={() => void openSummary(attendee)}>{attendee.full_name}</button>
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
                    <p className="text-xs font-bold uppercase tracking-widest text-stone-500">Larp Score</p>
                    <p className="text-xl font-black">{summary.larp_score != null ? summary.larp_score.toFixed(2) : "No data"}</p>
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
                          <p className="text-xs font-bold text-stone-600">Haiku LARP score</p>
                          <p className="text-lg font-black text-stone-950">{summary.comparison.larp_score.toFixed(2)}</p>
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
                      <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4 space-y-3">
                        <div className="flex items-center gap-3">
                          {(summary.linkedin.photoUrl ?? summary.linkedin.image) && (
                            <img className="h-14 w-14 rounded-full object-cover ring-2 ring-white shrink-0" src={summary.linkedin.photoUrl ?? summary.linkedin.image ?? ""} alt="LinkedIn" />
                          )}
                          <div>
                            <p className="font-bold text-blue-900">{summary.linkedin.name ?? selectedAttendee.full_name}</p>
                            {summary.linkedin.headline && <p className="text-sm text-blue-800">{summary.linkedin.headline}</p>}
                            {summary.linkedin.location && <p className="text-xs text-blue-600">📍 {summary.linkedin.location}</p>}
                          </div>
                        </div>
                        {summary.linkedin.about && (
                          <div>
                            <p className="mb-1 text-xs font-bold text-blue-700">About</p>
                            <p className="text-sm text-blue-900 line-clamp-4">{summary.linkedin.about}</p>
                          </div>
                        )}
                        {summary.linkedin.experiences && summary.linkedin.experiences.length > 0 && (
                          <div>
                            <p className="mb-1.5 text-xs font-bold text-blue-700">Experience</p>
                            <div className="space-y-1.5">
                              {summary.linkedin.experiences.map((exp, i) => (
                                <div key={i} className="rounded-lg bg-white/60 px-3 py-2 text-sm">
                                  <p className="font-semibold text-blue-900">{exp.title}</p>
                                  {exp.company && <p className="text-blue-700">{exp.company}</p>}
                                  {exp.dates && <p className="text-xs text-blue-500">{exp.dates}</p>}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {summary.linkedin.education && summary.linkedin.education.length > 0 && (
                          <div>
                            <p className="mb-1.5 text-xs font-bold text-blue-700">Education</p>
                            <div className="space-y-1">
                              {summary.linkedin.education.map((edu, i) => (
                                <div key={i} className="rounded-lg bg-white/60 px-3 py-2 text-sm">
                                  <p className="font-semibold text-blue-900">{edu.school}</p>
                                  {edu.degree && <p className="text-blue-700">{edu.degree}</p>}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {summary.linkedin.skills && summary.linkedin.skills.length > 0 && (
                          <div>
                            <p className="mb-1.5 text-xs font-bold text-blue-700">Skills</p>
                            <div className="flex flex-wrap gap-1.5">
                              {summary.linkedin.skills.map((s) => (
                                <span key={s} className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-bold text-blue-800">{s}</span>
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
                    <div className="rounded-2xl border border-stone-200 bg-white p-4">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-bold">{summary.github.name ?? summary.github.login}</p>
                          {summary.github.bio && <p className="mt-1 text-sm text-stone-600">{summary.github.bio}</p>}
                          {summary.github.company && <p className="mt-1 text-sm text-stone-500">🏢 {summary.github.company}</p>}
                          {summary.github.location && <p className="text-sm text-stone-500">📍 {summary.github.location}</p>}
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-1 text-sm">
                          <span className="font-bold">{summary.github.public_repos ?? 0} repos</span>
                          <span className="text-stone-500">{summary.github.followers ?? 0} followers</span>
                        </div>
                      </div>

                      {summary.github.top_languages && summary.github.top_languages.length > 0 && (
                        <div className="mt-3">
                          <p className="mb-1.5 text-xs font-bold text-stone-500">Top languages</p>
                          <div className="flex flex-wrap gap-1.5">
                            {summary.github.top_languages.map((lang) => (
                              <span key={lang} className="rounded-full bg-stone-100 px-2.5 py-1 text-xs font-bold text-stone-700">{lang}</span>
                            ))}
                          </div>
                        </div>
                      )}

                      {summary.github.recent_repos && summary.github.recent_repos.length > 0 && (
                        <div className="mt-3">
                          <p className="mb-1.5 text-xs font-bold text-stone-500">Recent repos</p>
                          <div className="space-y-1.5">
                            {summary.github.recent_repos.map((repo) => (
                              <a key={repo.name} href={repo.url} target="_blank" rel="noreferrer" className="flex items-center justify-between rounded-lg border border-stone-100 px-3 py-2 text-sm hover:bg-stone-50">
                                <span className="font-medium text-stone-800">{repo.name}</span>
                                <span className="text-stone-400">⭐ {repo.stars}</span>
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
