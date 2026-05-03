"use client";

import { use, useEffect, useState } from "react";
import { api, Event, EventFlag } from "@/lib/api";

function severityClass(severity: string | undefined) {
  if (severity === "high") return "score-text-high";
  if (severity === "medium") return "score-text-mid";
  return "score-text-low";
}

export default function FlagsPage({ params }: { params: Promise<{ eventId: string }> }) {
  const { eventId } = use(params);
  const [event, setEvent] = useState<Event | null>(null);
  const [flags, setFlags] = useState<EventFlag[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        setError(null);
        const [eventRes, flagsRes] = await Promise.all([api.event(eventId), api.flags(eventId)]);
        setEvent(eventRes.event);
        setFlags(flagsRes.flags);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load flags");
      } finally {
        setLoading(false);
      }
    }

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
          <p className="mt-2 text-xs text-stone-400">{event?.name ?? "EVENT"} · FLAGS</p>
        </div>
        <nav className="flex flex-wrap gap-3 text-[10px]">
          <a className="px-3 py-2" href={`/events/${eventId}`}>ATTENDEES</a>
          <a className="px-3 py-2" href={`/leaderboard?event_id=${encodeURIComponent(eventId)}`}>LARPERBOARD</a>
          <a className="px-3 py-2" href={`/events/${eventId}/live`}>LIVE</a>
        </nav>
      </header>
      <div className="pixel-strip" />

      <section className="mx-auto mt-10 max-w-6xl">
        <div className="rounded-lg border-2 border-yellow-500 bg-yellow-50 p-4 mb-4 text-center">
          <p className="text-sm font-bold text-yellow-800">⚠️ Flags are not being updated in real-time as this requires our hardware integration.</p>
        </div>
        <div className="flex items-center justify-between bg-black px-6 py-5 text-white border-2 border-black rounded-t-lg">
          <h1 className="text-2xl">RECENT FLAGS</h1>
          <span className="text-xs text-stone-300">LIVE FEED</span>
        </div>
        {loading ? <p className="p-6 text-sm">Loading flags...</p> : null}
        {error ? <p className="m-6 bg-red-100 p-4 text-sm text-red-800">{error}</p> : null}
        {!loading && flags.length === 0 ? <p className="p-6 text-sm">No flags raised in this event.</p> : null}
        <div>
          {flags.map((flag, index) => (
            <div
              key={flag.id}
              className={`grid gap-4 px-6 py-5 text-sm md:grid-cols-[120px_1fr_160px_120px] ${index % 2 ? "bg-[#b9b9b9]" : "bg-white"}`}
            >
              <span className={`font-bold uppercase ${severityClass(flag.severity)}`}>{flag.severity ?? "low"}</span>
              <div>
                <p>{flag.verified_text ?? flag.explanation ?? flag.claim_text ?? "Claim mismatch detected"}</p>
                <p className="mt-2 text-xs text-stone-600">{flag.attendee_name ?? "Unknown attendee"} · {flag.session_id ?? "session"}</p>
              </div>
              <span className="text-center">{flag.score_delta != null ? Math.round(flag.score_delta * 100) : "--"}</span>
              <span className="text-right uppercase">{String(flag.dispute_status ?? "open")}</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
