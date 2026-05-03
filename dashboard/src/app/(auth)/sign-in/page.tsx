"use client";

import { FormEvent, useState } from "react";
import { api, setToken } from "@/lib/api";

export default function SignInPage() {
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const res = await api.signIn("organizer@larpchekr.app");
      setToken(res.jwt);
      window.location.href = "/events";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    }
  }

  return (
    <main className="arcade-page p-10">
      <form onSubmit={submit} className="mx-auto mt-24 max-w-md border-2 border-black bg-white p-8">
        <p className="text-sm font-bold uppercase text-stone-600">L4RPCH3KR</p>
        <h1 className="mt-3 text-3xl font-black">ORGANIZER SIGN-IN</h1>
        <p className="mt-2 text-sm text-stone-600">Magic-link stub for day-one dashboard integration.</p>
        <button className="mt-6 w-full px-4 py-3 font-bold">Sign In</button>
        {error ? <p className="mt-4 text-sm text-red-700">{error}</p> : null}
      </form>
    </main>
  );
}
