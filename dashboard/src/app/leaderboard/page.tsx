"use client";

import { useEffect, useMemo, useState } from "react";
import { api, apiWsUrl, Event, Flag, LeaderboardEntry, WsEnvelope } from "@/lib/api";

function scoreClass(score: number) {
  if (score >= 0.75) return "score-text-high";
  if (score >= 0.35) return "score-text-mid";
  return "score-text-low";
}

export default function GlobalLeaderboardPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [eventId, setEventId] = useState("");
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const selectedEvent = useMemo(
    () => events.find((event) => event.id === eventId),
    [eventId, events],
  );

  async function load(nextEventId = eventId) {
    try {
      setLoading(true);
      setError(null);
      const [eventsRes, leaderboardRes] = await Promise.all([
        api.events(),
        api.leaderboard(nextEventId || undefined),
      ]);
      setEvents(eventsRes.events);
      setLeaderboard(leaderboardRes.leaderboard);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load larperboard");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!localStorage.getItem("larpchekr_jwt")) {
      window.location.href = "/sign-in";
      return;
    }
    const params = new URLSearchParams(window.location.search);
    const initialEventId = params.get("event_id") ?? "";
    setEventId(initialEventId);
    void load(initialEventId);

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
        setLeaderboard((rows) => {
          const updated = rows.map((e) =>
            e.attendee.id === subjectId ? { ...e, larp_score: Math.max(newScore, e.larp_score) } : e
          );
          // re-sort: highest larp_score first, then flag_count
          return [...updated].sort((a, b) => b.larp_score - a.larp_score || b.flag_count - a.flag_count)
            .map((e, i) => ({ ...e, rank: i + 1 }));
        });
      } else if (env.type === "flag_raised" && env.data.flag) {
        const flag = env.data.flag as Flag;
        const subjectId = flag.subject_id;
        if (subjectId) {
          setLeaderboard((rows) => {
            const updated = rows.map((e) =>
              e.attendee.id === subjectId ? { ...e, flag_count: e.flag_count + 1 } : e
            );
            return [...updated].sort((a, b) => b.larp_score - a.larp_score || b.flag_count - a.flag_count)
              .map((e, i) => ({ ...e, rank: i + 1 }));
          });
        }
      }
    };
    return () => ws.close();
  }, []);

  return (
    <main className="arcade-page">
      <header className="arcade-masthead">
        <div>
          <div className="arcade-wordmark">LarpChecker</div>
          <p className="mt-2 text-xs text-stone-400">
            {selectedEvent?.name ?? "GLOBAL"} · LARPERBOARD
          </p>
        </div>
        <nav className="flex flex-wrap gap-3 text-[10px]">
          <a className="px-3 py-2" href="/events">EVENTS</a>
          {eventId ? <a className="px-3 py-2" href={`/events/${eventId}`}>ATTENDEES</a> : null}
          {eventId ? <a className="px-3 py-2" href={`/events/${eventId}/flags`}>FLAGS</a> : null}
          <a className="px-3 py-2" href="/settings">SETTINGS</a>
        </nav>
      </header>
      <div className="pixel-strip" />

      <section className="mx-auto mt-10 max-w-6xl border-2 border-black bg-white">
        <div className="flex flex-wrap items-center justify-between gap-4 bg-black px-6 py-5 text-white">
          <div>
            <h1 className="text-2xl">LARPERBOARD</h1>
            <p className="mt-2 text-xs text-stone-300">Highest larp first. Filter by event or view all.</p>
          </div>
          <select
            className="border-2 border-white bg-black px-3 py-2 text-xs text-white"
            value={eventId}
            onChange={(e) => {
              const next = e.target.value;
              setEventId(next);
              const url = next ? `/leaderboard?event_id=${encodeURIComponent(next)}` : "/leaderboard";
              window.history.replaceState(null, "", url);
              void load(next);
            }}
          >
            <option value="">ALL EVENTS</option>
            {events.map((event) => (
              <option key={event.id} value={event.id}>{event.name}</option>
            ))}
          </select>
        </div>
        {loading ? <p className="p-6 text-sm">Loading larperboard...</p> : null}
        {error ? <p className="m-6 bg-red-100 p-4 text-sm text-red-800">{error}</p> : null}
        {!loading && leaderboard.length === 0 ? <p className="p-6 text-sm">No attendees on this board.</p> : null}
        {leaderboard.length > 0 ? (
          <div className="overflow-x-auto">
            <div className="grid min-w-[860px] grid-cols-[90px_1fr_180px_140px_180px] bg-black px-6 py-4 text-sm text-white">
              <span>RANK</span>
              <span>NAME</span>
              <span className="text-center">LARP</span>
              <span className="text-center">FLAGS</span>
              <span className="text-right">EVENT</span>
            </div>
            {leaderboard.map((entry, index) => {
              const eventName = events.find((event) => event.id === entry.attendee.event_id)?.name ?? entry.attendee.event_id;
              return (
                <a
                  key={`${entry.attendee.event_id}-${entry.attendee.id}`}
                  className={`grid min-w-[860px] grid-cols-[90px_1fr_180px_140px_180px] px-6 py-5 text-sm ${index % 2 ? "bg-[#b9b9b9]" : "bg-white"}`}
                  href={`/events/${entry.attendee.event_id}`}
                >
                  <span>#{entry.rank}</span>
                  <span>{entry.attendee.full_name}</span>
                  <span className={`text-center text-lg ${scoreClass(entry.larp_score)}`}>{Math.round(entry.larp_score * 100)}</span>
                  <span className="text-center">{entry.flag_count}</span>
                  <span className="truncate text-right">{eventName}</span>
                </a>
              );
            })}
          </div>
        ) : null}
      </section>
    </main>
  );
}
