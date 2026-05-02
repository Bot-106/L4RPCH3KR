"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { api, Event } from "@/lib/api";

export default function EventsPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [name, setName] = useState("Demo Hackathon");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      setLoading(true);
      setError(null);
      setEvents((await api.events()).events);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load events");
    } finally {
      setLoading(false);
    }
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Event name is required.");
      return;
    }
    try {
      setError(null);
      const res = await api.createEvent(trimmed);
      window.location.href = `/events/${res.event.id}`;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create event");
    }
  }

  useEffect(() => {
    if (!localStorage.getItem("larpchekr_jwt")) {
      window.location.href = "/sign-in";
      return;
    }
    void load();
  }, []);

  return (
    <main className="arcade-page">
      <header className="arcade-masthead">
        <div className="flex items-center gap-5">
          <div className="arcade-mark" aria-hidden="true">
            <i /><i /><i className="w" /><i className="w" /><i className="w" /><i className="w" /><i /><i />
            <i /><i className="w" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="w" /><i />
            <i className="w" /><i className="g" /><i className="g" /><i className="w" /><i className="w" /><i className="g" /><i className="g" /><i className="w" />
            <i className="w" /><i className="g" /><i className="w" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="w" />
            <i className="w" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="w" />
            <i className="w" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="w" />
            <i /><i className="w" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="w" /><i />
            <i /><i /><i className="w" /><i className="w" /><i className="w" /><i className="w" /><i /><i />
          </div>
          <div className="arcade-wordmark">LarpChecker</div>
        </div>
        <nav className="flex flex-wrap gap-3 text-[10px]">
          <span className="bg-white px-3 py-2 text-black">EVENTS</span>
          <a className="px-3 py-2 text-white" href="/leaderboard">LARPERBOARD</a>
          <span className="px-3 py-2 text-white">FLAGS</span>
        </nav>
      </header>
      <div className="pixel-strip" />
      <div className="mx-auto max-w-5xl p-10">
        <h1 className="text-4xl font-black tracking-tight">EVENTS</h1>
        <p className="mt-3 text-stone-600">Pick an event, import attendees, and export the enriched CSV.</p>
        <form onSubmit={create} className="mt-8 flex gap-3 border border-stone-300 bg-white p-4">
          <input className="flex-1 rounded-xl border border-stone-300 px-4 py-3" value={name} onChange={(e) => setName(e.target.value)} aria-label="Event name" />
          <button className="px-5 py-3 font-bold">Create event</button>
        </form>
        {loading ? <p className="mt-8">Loading events...</p> : null}
        {error ? <p className="mt-8 rounded-xl bg-red-100 p-4 text-red-800">{error}</p> : null}
        {!loading && events.length === 0 ? (
          <div className="mt-8 rounded-3xl border border-dashed border-stone-400 bg-white p-6">
            <h2 className="text-2xl font-bold">No events yet</h2>
            <p className="mt-1 text-stone-600">Create the first event above to start importing attendees.</p>
          </div>
        ) : null}
        <div className="mt-8 grid gap-4">
          {events.map((event) => (
            <Link key={event.id} href={`/events/${event.id}`} className="border-2 border-black bg-white p-6 transition">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-black">{event.name}</h2>
                  <p className="text-sm text-stone-600">{new Date(event.starts_at).toLocaleString()}</p>
                </div>
                <span className="rounded-full bg-stone-950 px-4 py-2 text-sm font-bold text-white">Open</span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
