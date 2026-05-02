"use client";

import { use, useEffect, useRef, useState } from "react";
import { api, apiWsUrl, Attendee, Claim, Event, Flag, getToken, Utterance, WsEnvelope } from "@/lib/api";

type CaptureStatus = "idle" | "requesting_media" | "ready" | "connecting" | "live" | "stopped" | "error";

type BrowserAudioWindow = Window & typeof globalThis & { webkitAudioContext?: typeof AudioContext };
type SttStatus = "unknown" | "backend" | "stopped";
type SubjectIdentity = {
  attendee_id: string | null;
  attendee?: Attendee | null;
  confidence: number;
  method: string;
  reason?: string;
};

function envelope(type: string, data: Record<string, unknown>, sessionId?: string | null) {
  return {
    id: crypto.randomUUID(),
    type,
    ts: new Date().toISOString(),
    session_id: sessionId ?? null,
    data
  };
}

function floatTo16BitPcm(input: Float32Array) {
  const output = new ArrayBuffer(input.length * 2);
  const view = new DataView(output);
  for (let i = 0; i < input.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, input[i]));
    view.setInt16(i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
  return output;
}

function scoreVerdict(score: number | null) {
  if (score == null) return "Waiting for evidence";
  if (score >= 0.66) return "LARPING HARD";
  if (score >= 0.33) return "Possibly larping";
  return "Probably not larping";
}

function larpPercent(score: number | null) {
  return Math.round(Math.min(1, Math.max(0, score ?? 0)) * 100);
}

function larpAssessment(score: number | null, flags: Flag[]) {
  if (flags.length === 0) return "No larp detected yet";
  if ((score ?? 0) >= 0.66) return "Likely larping";
  if ((score ?? 0) >= 0.33) return "Suspicious claim detected";
  return "Low-confidence larp signal";
}

export default function LaptopLivePage({ params }: { params: Promise<{ eventId: string }> }) {
  const { eventId } = use(params);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const mediaRef = useRef<MediaStream | null>(null);
  const piWsRef = useRef<WebSocket | null>(null);
  const phoneWsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const audioSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const snapshotRef = useRef<number | null>(null);

  const [event, setEvent] = useState<Event | null>(null);
  const [status, setStatus] = useState<CaptureStatus>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [utterances, setUtterances] = useState<Utterance[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [flags, setFlags] = useState<Flag[]>([]);
  const [score, setScore] = useState<number | null>(null);
  const [scoreLabel, setScoreLabel] = useState<string>("no score yet");
  const [lastHaptic, setLastHaptic] = useState<string | null>(null);
  const [sttStatus, setSttStatus] = useState<SttStatus>("unknown");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [subject, setSubject] = useState<SubjectIdentity | null>(null);

  const isLive = status === "live" || status === "connecting" || status === "ready";

  function sendPiJson(type: string, data: Record<string, unknown>, sid = sessionId) {
    const ws = piWsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(envelope(type, data, sid)));
    }
  }

  function stopCapture(nextStatus: CaptureStatus = "stopped") {
    if (sessionId) {
      sendPiJson("session_end", { session_id: sessionId, reason: "browser_stop" }, sessionId);
    }
    if (heartbeatRef.current) window.clearInterval(heartbeatRef.current);
    if (snapshotRef.current) window.clearInterval(snapshotRef.current);
    heartbeatRef.current = null;
    snapshotRef.current = null;
    audioProcessorRef.current?.disconnect();
    audioSourceRef.current?.disconnect();
    audioContextRef.current?.close().catch(() => undefined);
    audioProcessorRef.current = null;
    audioSourceRef.current = null;
    audioContextRef.current = null;
    piWsRef.current?.close();
    phoneWsRef.current?.close();
    piWsRef.current = null;
    phoneWsRef.current = null;
    mediaRef.current?.getTracks().forEach((track) => track.stop());
    mediaRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setStatus(nextStatus);
    setSttStatus("stopped");
  }

  function startAudioStreaming(stream: MediaStream, sid: string) {
    const AudioContextCtor = window.AudioContext || (window as BrowserAudioWindow).webkitAudioContext;
    if (!AudioContextCtor) throw new Error("This browser does not support Web Audio capture.");
    const context = new AudioContextCtor({ sampleRate: 16000 });
    const source = context.createMediaStreamSource(stream);
    const processor = context.createScriptProcessor(4096, 1, 1);
    let chunks: Float32Array[] = [];
    let bufferedSamples = 0;

    processor.onaudioprocess = (event) => {
      const input = event.inputBuffer.getChannelData(0);
      const copied = new Float32Array(input.length);
      copied.set(input);
      chunks.push(copied);
      bufferedSamples += copied.length;

      if (bufferedSamples < context.sampleRate) return;
      const merged = new Float32Array(bufferedSamples);
      let offset = 0;
      for (const chunk of chunks) {
        merged.set(chunk, offset);
        offset += chunk.length;
      }
      chunks = [];
      bufferedSamples = 0;
      const ws = piWsRef.current;
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(floatTo16BitPcm(merged));
      }
    };

    source.connect(processor);
    processor.connect(context.destination);
    audioContextRef.current = context;
    audioSourceRef.current = source;
    audioProcessorRef.current = processor;
    sendPiJson("audio_meta", { session_id: sid, sample_rate_hz: 16000, channels: 1, encoding: "pcm_s16le", speaker_hint: "partner", source: "browser" }, sid);
  }

  function sendSnapshot(sid: string) {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.videoWidth === 0) return;
    const width = Math.min(video.videoWidth, 640);
    const height = Math.round((width / video.videoWidth) * video.videoHeight);
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.drawImage(video, 0, 0, width, height);
    const imageB64 = canvas.toDataURL("image/jpeg", 0.72).split(",")[1];
    sendPiJson("frame_snapshot", { session_id: sid, event_id: eventId, image_b64: imageB64, width, height, source: "browser" }, sid);
  }

  async function startLiveCheck() {
    try {
      setError(null);
      setStatus("requesting_media");
      if (!getToken()) {
        window.location.href = "/sign-in";
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" } });
      mediaRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setStatus("ready");

      const created = await api.createSession(eventId, "browser-laptop");
      const sid = created.session.id;
      setSessionId(sid);
      setScore(created.session.score ?? 0);
      setScoreLabel(created.session.score_label ?? "mostly honest");
      setStatus("connecting");

      const piWs = new WebSocket(apiWsUrl("/ws/pi"));
      const phoneWs = new WebSocket(apiWsUrl("/ws/phone"));
      piWsRef.current = piWs;
      phoneWsRef.current = phoneWs;

      phoneWs.onopen = () => {
        phoneWs.send(JSON.stringify(envelope("subscribe_session", { session_id: sid }, sid)));
      };
      phoneWs.onmessage = (message) => {
        const parsed = JSON.parse(message.data as string) as WsEnvelope<Record<string, unknown>>;
        if (parsed.type === "transcript_update" && "utterances" in parsed.data) {
          setUtterances((rows) => [...rows, ...(parsed.data.utterances as Utterance[])].slice(-30));
        } else if (parsed.type === "claim_detected" && "claim" in parsed.data) {
          setClaims((rows) => [parsed.data.claim as Claim, ...rows].slice(0, 20));
        } else if (parsed.type === "flag_raised" && "flag" in parsed.data) {
          const flag = parsed.data.flag as Flag;
          setFlags((rows) => [flag, ...rows].slice(0, 20));
          const delta = typeof flag.score_delta === "number" ? flag.score_delta : typeof flag.larp_score_delta === "number" ? flag.larp_score_delta : 0;
          if (delta) setScore((current) => Math.min(1, (current ?? 0) + delta));
        } else if (parsed.type === "score_update" && "score" in parsed.data) {
          setScore(Number(parsed.data.score));
          setScoreLabel(String(parsed.data.label));
        } else if (parsed.type === "subject_identified") {
          setSubject(parsed.data as SubjectIdentity);
        } else if (parsed.type === "error" && "message" in parsed.data) {
          setError(String(parsed.data.message));
        }
      };
      phoneWs.onerror = () => setError("Phone-style live feed socket failed.");

      piWs.onopen = () => {
        piWs.send(JSON.stringify(envelope("pi_hello", { device_id: "browser-laptop", firmware_version: "dashboard-browser", battery_pct: null }, sid)));
        piWs.send(JSON.stringify(envelope("session_start", { session_id: sid, source: "browser" }, sid)));
        startAudioStreaming(stream, sid);
        setSttStatus("backend");
        sendSnapshot(sid);
        heartbeatRef.current = window.setInterval(() => sendPiJson("heartbeat", { session_id: sid, battery_pct: null, cpu_temp_c: null, buffer_seconds: 0, source: "browser" }, sid), 10000);
        snapshotRef.current = window.setInterval(() => sendSnapshot(sid), 10000);
        setStatus("live");
      };
      piWs.onmessage = (message) => {
        const parsed = JSON.parse(message.data as string) as WsEnvelope<{ severity?: string; pattern?: number[]; message?: string }>;
        if (parsed.type === "haptic_pulse") {
          setLastHaptic(`${parsed.data.severity ?? "medium"} pulse`);
        } else if (parsed.type === "subject_resolved") {
          setSubject(parsed.data as SubjectIdentity);
        } else if (parsed.type === "error") {
          setError(parsed.data.message ?? "Pi socket error");
        }
      };
      piWs.onerror = () => setError("Pi-style capture socket failed.");
      piWs.onclose = () => {
        if (status === "live") setStatus("stopped");
      };
    } catch (err) {
      stopCapture("error");
      setError(err instanceof Error ? err.message : "Could not start laptop capture");
    }
  }

  useEffect(() => {
    if (!localStorage.getItem("larpchekr_jwt")) {
      window.location.href = "/sign-in";
      return;
    }
    api.event(eventId).then((res) => setEvent(res.event)).catch((err: unknown) => setError(err instanceof Error ? err.message : "Event load failed"));
    return () => stopCapture("stopped");
  }, [eventId]);

  return (
    <main className="min-h-screen bg-[#10100f] p-4 text-stone-50 md:p-8">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <a className="text-sm font-bold text-orange-300" href={`/events/${eventId}`}>Back to event</a>
            <h1 className="mt-2 text-4xl font-black tracking-tight md:text-6xl">Laptop LARP check</h1>
            <p className="mt-2 text-stone-300">{event?.name ?? "Loading event..."} · browser mic/camera, Pi path still supported</p>
          </div>
          <div className="flex gap-3">
            <button className="rounded-2xl bg-lime-300 px-5 py-3 font-black text-stone-950 disabled:cursor-not-allowed disabled:opacity-50" disabled={isLive} onClick={() => void startLiveCheck()}>Start laptop check</button>
            <button className="rounded-2xl border border-stone-600 px-5 py-3 font-black text-stone-100" onClick={() => stopCapture()}>Stop</button>
          </div>
        </div>

        {error ? <p className="mt-5 rounded-2xl border border-red-500/40 bg-red-950/60 p-4 text-sm text-red-100">{error}</p> : null}

        <section className="mt-6 grid gap-4 lg:grid-cols-[1.35fr_0.65fr]">
          <div className="overflow-hidden rounded-[2rem] border border-stone-700 bg-black shadow-2xl shadow-black/50">
            <video ref={videoRef} className="aspect-video w-full object-cover" muted playsInline />
            <canvas ref={canvasRef} className="hidden" />
          </div>
          <div className="grid gap-4">
            <div className="rounded-[2rem] border border-lime-300/40 bg-lime-300 p-6 text-stone-950">
              <p className="text-xs font-black uppercase tracking-[0.25em]">Verdict</p>
              <p className="mt-3 text-4xl font-black">{scoreVerdict(score)}</p>
              <div className="mt-4 rounded-2xl bg-stone-950 p-4 text-white">
                <p className="text-xs font-black uppercase tracking-[0.25em] text-lime-200">Larp probability</p>
                <p className="mt-1 text-5xl font-black">{larpPercent(score)}%</p>
                <p className="mt-1 text-sm font-bold text-lime-100">{larpAssessment(score, flags)}</p>
              </div>
              <p className="mt-2 text-sm font-bold">Score {score == null ? "--" : score.toFixed(2)} · {scoreLabel} · {flags.length} flags</p>
            </div>
            <div className="rounded-[2rem] border border-stone-700 bg-stone-900 p-6">
              <p className="text-xs font-black uppercase tracking-[0.25em] text-stone-400">Capture</p>
              <dl className="mt-4 grid gap-3 text-sm">
                <div className="flex justify-between gap-3"><dt className="text-stone-400">Status</dt><dd className="font-bold">{status}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-stone-400">Speech-to-text</dt><dd className="font-bold">{sttStatus}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-stone-400">Session</dt><dd className="truncate font-mono text-xs">{sessionId ?? "not started"}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-stone-400">Flags</dt><dd className="font-bold">{flags.length}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-stone-400">Haptic mirror</dt><dd className="font-bold">{lastHaptic ?? "none"}</dd></div>
              </dl>
            </div>
          </div>
        </section>

        <section className="mt-6 grid gap-4 lg:grid-cols-3">
          <div className="rounded-[2rem] border border-stone-700 bg-stone-900 p-5 lg:col-span-2">
            <h2 className="text-xl font-black">Live transcript</h2>
            <div className="mt-4 space-y-3">
              {interimTranscript ? (
                <article className="rounded-2xl border border-orange-300/40 bg-orange-950/30 p-4">
                  <p className="text-xs font-black uppercase tracking-widest text-orange-300">browser interim</p>
                  <p className="mt-2 text-sm text-stone-100">{interimTranscript}</p>
                </article>
              ) : null}
              {utterances.map((utterance) => (
                <article key={utterance.id} className="rounded-2xl bg-stone-800 p-4">
                  <p className="text-xs font-black uppercase tracking-widest text-orange-300">speaker: {utterance.speaker}</p>
                  <p className="mt-2 text-sm text-stone-100">{utterance.text || utterance.transcript}</p>
                </article>
              ))}
              {!utterances.length && !interimTranscript ? <p className="rounded-2xl bg-stone-800 p-4 text-sm text-stone-400">Start capture and talk. Audio is streamed to backend ASR for transcription.</p> : null}
            </div>
          </div>

          <div className="rounded-[2rem] border border-stone-700 bg-stone-900 p-5">
            <h2 className="text-xl font-black">Flags</h2>
            <div className="mt-4 space-y-3">
              {flags.map((flag) => (
                <article key={flag.id} className="rounded-2xl border border-red-400/40 bg-red-950/50 p-4">
                  <p className="text-xs font-black uppercase tracking-widest text-red-200">{flag.severity}</p>
                  <p className="mt-2 text-sm font-bold">{flag.claim_text ?? "Claim flagged"}</p>
                  <p className="mt-2 text-xs text-red-100">{flag.verified_text ?? flag.explanation ?? "Backend raised a discrepancy."}</p>
                </article>
              ))}
              {!flags.length ? <p className="rounded-2xl bg-stone-800 p-4 text-sm text-stone-400">No flags yet.</p> : null}
            </div>
          </div>
        </section>

        <section className="mt-4 rounded-[2rem] border border-stone-700 bg-stone-900 p-5">
          <h2 className="text-xl font-black">Claims</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {claims.map((claim) => (
              <article key={claim.id} className="rounded-2xl bg-stone-800 p-4 text-sm text-stone-200">
                <p className="font-bold">{claim.claim_text ?? claim.text ?? "Detected claim"}</p>
                <p className="mt-2 text-xs text-stone-400">{claim.type ?? "claim"} · {typeof claim.confidence === "number" ? `${(claim.confidence * 100).toFixed(0)}%` : "confidence pending"}</p>
              </article>
            ))}
            {!claims.length ? <p className="text-sm text-stone-400">Claims will appear when the backend extracts them.</p> : null}
          </div>
        </section>

        <div className="mt-6 flex justify-center">
          <button
            onClick={() => {
              setFlags([]);
              setScore(0);
              setScoreLabel("flags cleared");
            }}
            disabled={flags.length === 0}
            className="rounded-2xl border border-red-500/40 bg-red-950/60 px-6 py-3 font-black text-red-100 hover:bg-red-950 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Clear flags
          </button>
        </div>
      </div>
    </main>
  );
}
