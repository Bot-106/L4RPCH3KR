"""
Audio capture with VAD gating and on-device STT.

Real mode: sounddevice, 16kHz mono PCM s16le, 250ms frames.
Fake mode: sends browser_transcript text events on a timer.

VAD logic (real mode):
  - Split each 250ms frame into 25 × 10ms sub-frames.
  - Run webrtcvad aggressiveness=2 on each.
  - If ≥ SPEECH_RATIO are speech → chunk is speech.
  - SPEAKING → SILENT: after HANGOVER_FRAMES consecutive silent chunks,
    collect the buffered PCM, run faster-whisper locally, and send a
    browser_transcript envelope with the transcript text.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC

log = logging.getLogger(__name__)

# Fake-mode transcript phrases cycled in order
_FAKE_PHRASES = [
    "Hi, I'm a software engineer at Google with ten years of experience in distributed systems.",
    "I've published three papers on machine learning and hold a degree from MIT.",
    "My open-source project has over five thousand stars on GitHub.",
    "I led the team that built the infrastructure for a major cloud provider.",
]

SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_MS = 250
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 4 000 samples
BYTES_PER_SAMPLE = 2
FRAME_BYTES = FRAME_SAMPLES * BYTES_PER_SAMPLE  # 8 000 bytes

# webrtcvad parameters
VAD_FRAME_MS = 10  # must be 10, 20, or 30
VAD_FRAME_SAMPLES = SAMPLE_RATE * VAD_FRAME_MS // 1000  # 160
VAD_FRAME_BYTES = VAD_FRAME_SAMPLES * BYTES_PER_SAMPLE  # 320
VAD_SUB_FRAMES = FRAME_MS // VAD_FRAME_MS  # 25 sub-frames per chunk
SPEECH_RATIO = 0.4  # fraction of sub-frames that must be speech

# How many consecutive silent frames before we stop sending
HANGOVER_FRAMES = 8  # 8 × 250ms = 2s hangover

# Force transcription flush when VAD is stuck in speech (noisy environment)
MAX_SEGMENT_BYTES = SAMPLE_RATE * BYTES_PER_SAMPLE * 10  # 10s × 32000 B/s

SendEnvelopeFn = Callable[[dict], Awaitable[None]]
TranscriptCallback = Callable[[str], None]


def _make_browser_transcript_envelope(text: str, session_id: str | None, face_ratio: float = 1.0) -> dict:
    import uuid
    from datetime import datetime
    return {
        "id": uuid.uuid4().hex,
        "type": "browser_transcript",
        "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "session_id": session_id,
        "data": {
            "text": text,
            "speaker_hint": "subject",
            "face_ratio": round(face_ratio, 3),
            "session_id": session_id,
        },
    }


class AudioCapture:
    def __init__(self, fake: bool = False) -> None:
        self._fake = fake
        self._vad = None
        self._transcriber = None
        if not fake:
            try:
                import webrtcvad  # type: ignore[import]
                self._vad = webrtcvad.Vad(2)
            except Exception as exc:
                log.warning("audio: webrtcvad init failed (%s) — VAD disabled", exc)

    def _get_transcriber(self):
        if self._transcriber is None:
            from larpchekr.transcriber import Transcriber
            self._transcriber = Transcriber()
        return self._transcriber

    def _is_speech(self, pcm: bytes) -> bool:
        """Vote across 25 × 10ms sub-frames."""
        if self._vad is None:
            return True  # no VAD → always stream
        votes = 0
        for i in range(VAD_SUB_FRAMES):
            start = i * VAD_FRAME_BYTES
            frame = pcm[start : start + VAD_FRAME_BYTES]
            if len(frame) < VAD_FRAME_BYTES:
                break
            try:
                if self._vad.is_speech(frame, SAMPLE_RATE):
                    votes += 1
            except Exception:
                pass
        return (votes / VAD_SUB_FRAMES) >= SPEECH_RATIO

    async def run(
        self,
        send_envelope: SendEnvelopeFn,
        get_session_id: Callable[[], str | None],
        stop_event: asyncio.Event,
        on_transcript: TranscriptCallback | None = None,
        get_face_ratio: Callable[[], float] | None = None,
    ) -> None:
        if self._fake:
            await self._run_fake(send_envelope, get_session_id, stop_event, on_transcript)
        else:
            await self._run_real(send_envelope, get_session_id, stop_event, on_transcript, get_face_ratio)

    # ------------------------------------------------------------------
    # Fake mode — emit pre-written transcript phrases on a timer.
    # Face gate is bypassed in fake mode so tests always flow through.
    # ------------------------------------------------------------------
    async def _run_fake(
        self,
        send_envelope: SendEnvelopeFn,
        get_session_id: Callable[[], str | None],
        stop_event: asyncio.Event,
        on_transcript: TranscriptCallback | None = None,
    ) -> None:
        log.info("audio: FAKE mode — sending scripted transcript phrases every 8s")
        phrase_idx = 0
        while not stop_event.is_set():
            await asyncio.sleep(8.0)
            if stop_event.is_set():
                break
            session_id = get_session_id()
            if session_id is None:
                continue
            text = _FAKE_PHRASES[phrase_idx % len(_FAKE_PHRASES)]
            phrase_idx += 1
            log.debug("audio: fake transcript → %s", text[:60])
            if on_transcript:
                on_transcript(text)
            await send_envelope(_make_browser_transcript_envelope(text, session_id, face_ratio=1.0))

    # ------------------------------------------------------------------
    # Real mode — sounddevice callback fills an asyncio queue; on speech
    # end, accumulated PCM is transcribed locally and sent as text.
    # Only sends when face has been detected ≥70% of the 10s window.
    # ------------------------------------------------------------------
    async def _run_real(
        self,
        send_envelope: SendEnvelopeFn,
        get_session_id: Callable[[], str | None],
        stop_event: asyncio.Event,
        on_transcript: TranscriptCallback | None = None,
        get_face_ratio: Callable[[], float] | None = None,
    ) -> None:
        try:
            import numpy as np  # type: ignore[import]
            import sounddevice as sd  # type: ignore[import]
        except ImportError as exc:
            log.error("audio: sounddevice not available (%s) — audio disabled", exc)
            await stop_event.wait()
            return

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=64)

        def callback(indata: np.ndarray, frames: int, t: object, status: object) -> None:
            if status:
                log.debug("sounddevice status: %s", status)
            pcm = (indata[:, 0] * 32767).astype("int16").tobytes()
            try:
                loop.call_soon_threadsafe(queue.put_nowait, pcm)
            except asyncio.QueueFull:
                log.debug("audio queue full — dropping frame")

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=FRAME_SAMPLES,
            callback=callback,
        ):
            log.info("audio: sounddevice stream started")
            speaking = False
            silent_count = 0
            speech_pcm = bytearray()

            while not stop_event.is_set():
                try:
                    pcm = await asyncio.wait_for(queue.get(), timeout=0.5)
                except TimeoutError:
                    continue

                session_id = get_session_id()
                if session_id is None:
                    speaking = False
                    speech_pcm.clear()
                    continue

                is_sp = self._is_speech(pcm)

                if is_sp:
                    silent_count = 0
                    if not speaking:
                        speaking = True
                        speech_pcm.clear()
                        log.debug("audio: speech started")
                    speech_pcm.extend(pcm)
                    # Safety flush: VAD can get stuck at 100% in noisy environments.
                    # Force transcription after MAX_SEGMENT_BYTES so audio never
                    # accumulates indefinitely without producing a transcript.
                    if len(speech_pcm) >= MAX_SEGMENT_BYTES:
                        log.debug("audio: max segment reached — flushing %d bytes", len(speech_pcm))
                        captured = bytes(speech_pcm)
                        speech_pcm.clear()
                        speaking = False
                        silent_count = 0
                        transcriber = self._get_transcriber()
                        try:
                            text = await asyncio.wait_for(
                                loop.run_in_executor(None, transcriber.transcribe, captured),
                                timeout=45.0,
                            )
                        except asyncio.TimeoutError:
                            log.warning("audio: transcription timed out — skipping segment")
                            text = None
                        if text:
                            ratio = get_face_ratio() if get_face_ratio else 1.0
                            if ratio < 0.70:
                                log.info("audio: skip transcript (face_ratio=%.2f < 0.70) preview=%s", ratio, text[:40])
                            else:
                                log.info("audio: transcript → %s (face_ratio=%.2f)", text[:80], ratio)
                                if on_transcript:
                                    on_transcript(text)
                                await send_envelope(
                                    _make_browser_transcript_envelope(text, session_id, ratio)
                                )
                        else:
                            log.debug("audio: transcription returned empty")
                else:
                    if speaking:
                        speech_pcm.extend(pcm)  # include trailing frame in segment
                    silent_count += 1
                    if silent_count > HANGOVER_FRAMES:
                        if speaking and speech_pcm:
                            log.debug(
                                "audio: speech ended (%d bytes) — transcribing",
                                len(speech_pcm),
                            )
                            captured = bytes(speech_pcm)
                            speech_pcm.clear()
                            transcriber = self._get_transcriber()
                            try:
                                text = await asyncio.wait_for(
                                    loop.run_in_executor(None, transcriber.transcribe, captured),
                                    timeout=45.0,
                                )
                            except asyncio.TimeoutError:
                                log.warning("audio: transcription timed out — skipping segment")
                                text = None
                            if text:
                                ratio = get_face_ratio() if get_face_ratio else 1.0
                                if ratio < 0.70:
                                    log.info("audio: skip transcript (face_ratio=%.2f < 0.70) preview=%s", ratio, text[:40])
                                else:
                                    log.info("audio: transcript → %s (face_ratio=%.2f)", text[:80], ratio)
                                    if on_transcript:
                                        on_transcript(text)
                                    await send_envelope(
                                        _make_browser_transcript_envelope(text, session_id, ratio)
                                    )
                            else:
                                log.debug("audio: transcription returned empty")
                        speaking = False
                        continue
