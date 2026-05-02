"""
Audio capture with VAD gating.

Real mode: sounddevice, 16kHz mono PCM s16le, 250ms frames.
Fake mode: generated sine-wave audio, VAD always active.

Each binary frame is prefixed with an 8-byte int64 big-endian ms timestamp
so the backend can reorder within a 1-second window.

VAD logic (real mode):
  - Split each 250ms frame into 25 × 10ms sub-frames.
  - Run webrtcvad aggressiveness=2 on each.
  - If ≥ SPEECH_RATIO are speech → chunk is speech.
  - SILENT → SPEAKING: emit audio_meta envelope, then the frame.
  - SPEAKING  → SILENT: after HANGOVER_FRAMES consecutive silent chunks.
"""
from __future__ import annotations

import asyncio
import logging
import math
import struct
import time
from typing import Awaitable, Callable

log = logging.getLogger(__name__)

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

SendEnvelopeFn = Callable[[dict], Awaitable[None]]
SendBinaryFn = Callable[[bytes], Awaitable[None]]


def _make_audio_frame_header(ms: int) -> bytes:
    return struct.pack(">q", ms)


def _make_audio_meta_envelope(session_id: str | None) -> dict:
    import uuid
    from datetime import datetime, timezone
    return {
        "id": uuid.uuid4().hex,
        "type": "audio_meta",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "session_id": session_id,
        "data": {
            "sample_rate": SAMPLE_RATE,
            "encoding": "pcm_s16le",
            "channels": CHANNELS,
            "frame_ms": FRAME_MS,
            "speaker_hint": "self",
        },
    }


class AudioCapture:
    def __init__(self, fake: bool = False) -> None:
        self._fake = fake
        self._vad = None
        if not fake:
            try:
                import webrtcvad  # type: ignore[import]
                self._vad = webrtcvad.Vad(2)
            except Exception as exc:
                log.warning("audio: webrtcvad init failed (%s) — VAD disabled", exc)

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
        send_binary: SendBinaryFn,
        get_session_id: Callable[[], str | None],
        stop_event: asyncio.Event,
    ) -> None:
        if self._fake:
            await self._run_fake(send_envelope, send_binary, get_session_id, stop_event)
        else:
            await self._run_real(send_envelope, send_binary, get_session_id, stop_event)

    # ------------------------------------------------------------------
    # Fake mode — generate sine-wave audio so the WS round-trip can be
    # exercised without hardware. VAD is bypassed.
    # ------------------------------------------------------------------
    async def _run_fake(
        self,
        send_envelope: SendEnvelopeFn,
        send_binary: SendBinaryFn,
        get_session_id: Callable[[], str | None],
        stop_event: asyncio.Event,
    ) -> None:
        import struct as _struct

        log.info("audio: FAKE mode — generating sine-wave audio at 440 Hz")
        meta_sent = False
        phase = 0.0
        freq = 440.0
        amplitude = 8000  # well below int16 max

        while not stop_event.is_set():
            session_id = get_session_id()
            if session_id is None:
                await asyncio.sleep(0.1)
                meta_sent = False
                continue

            if not meta_sent:
                await send_envelope(_make_audio_meta_envelope(session_id))
                meta_sent = True

            # Generate 250ms of sine wave
            samples: list[int] = []
            for i in range(FRAME_SAMPLES):
                val = int(amplitude * math.sin(2 * math.pi * freq * (phase + i) / SAMPLE_RATE))
                samples.append(max(-32767, min(32767, val)))
            phase = (phase + FRAME_SAMPLES) % SAMPLE_RATE

            pcm = _struct.pack(f"<{FRAME_SAMPLES}h", *samples)
            ms = int(time.time() * 1000)
            header = _make_audio_frame_header(ms)
            await send_binary(header + pcm)

            await asyncio.sleep(FRAME_MS / 1000)

    # ------------------------------------------------------------------
    # Real mode — sounddevice callback fills an asyncio queue
    # ------------------------------------------------------------------
    async def _run_real(
        self,
        send_envelope: SendEnvelopeFn,
        send_binary: SendBinaryFn,
        get_session_id: Callable[[], str | None],
        stop_event: asyncio.Event,
    ) -> None:
        try:
            import sounddevice as sd  # type: ignore[import]
            import numpy as np  # type: ignore[import]
        except ImportError as exc:
            log.error("audio: sounddevice not available (%s) — audio disabled", exc)
            await stop_event.wait()
            return

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=64)

        def callback(indata: "np.ndarray", frames: int, t: object, status: object) -> None:
            if status:
                log.debug("sounddevice status: %s", status)
            # indata is float32 in [-1, 1]; convert to int16
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

            while not stop_event.is_set():
                try:
                    pcm = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue

                session_id = get_session_id()
                if session_id is None:
                    # No active session — don't send
                    speaking = False
                    continue

                is_sp = self._is_speech(pcm)

                if is_sp:
                    silent_count = 0
                    if not speaking:
                        speaking = True
                        await send_envelope(_make_audio_meta_envelope(session_id))
                        log.debug("audio: speech started")
                else:
                    silent_count += 1
                    if silent_count > HANGOVER_FRAMES:
                        if speaking:
                            log.debug("audio: silence detected — hangover expired")
                        speaking = False
                        continue

                if speaking:
                    ms = int(time.time() * 1000)
                    header = _make_audio_frame_header(ms)
                    await send_binary(header + pcm)
