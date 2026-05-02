"use client";

import { FormEvent, useState } from "react";
import { api, setToken } from "@/lib/api";

export default function SignInPage() {
  const [email, setEmail] = useState("organizer@example.com");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const res = await api.signIn(email);
      setToken(res.jwt);
      window.location.href = "/events";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    }
  }

  return (
    <main className="min-h-screen bg-stone-100 p-10 text-stone-950">
      <form onSubmit={submit} className="mx-auto mt-24 max-w-md rounded-3xl border border-stone-300 bg-white p-8 shadow-sm">
        <p className="text-sm font-bold uppercase tracking-[0.3em] text-orange-700">L4RPCH3KR</p>
        <h1 className="mt-3 text-3xl font-black">Organizer sign-in</h1>
        <p className="mt-2 text-sm text-stone-600">Magic-link stub for day-one dashboard integration.</p>
        <input className="mt-6 w-full rounded-xl border border-stone-300 px-4 py-3" value={email} onChange={(e) => setEmail(e.target.value)} type="email" />
        <button className="mt-4 w-full rounded-xl bg-stone-950 px-4 py-3 font-bold text-white">Continue</button>
        {error ? <p className="mt-4 text-sm text-red-700">{error}</p> : null}
      </form>
    </main>
  );
}
