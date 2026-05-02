"""
On-device speech-to-text using faster-whisper.

Model: tiny.en, int8 quantization — runs on Pi 5 CPU in ~0.5-1.5s per utterance.
The WhisperModel is loaded lazily on the first transcription call to avoid
blocking startup.
"""
from __future__ import annotations

import logging
import struct

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000


class Transcriber:
    def __init__(self, model_size: str = "tiny.en") -> None:
        self._model_size = model_size
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel  # type: ignore[import]
            log.info("transcriber: loading %s model (int8, cpu)…", self._model_size)
            self._model = WhisperModel(
                self._model_size,
                device="cpu",
                compute_type="int8",
            )
            log.info("transcriber: model ready")
        except Exception as exc:
            log.error("transcriber: model load failed: %s", exc)
            raise

    def transcribe(self, pcm_bytes: bytes, sample_rate: int = SAMPLE_RATE) -> str | None:
        """Transcribe raw s16le PCM bytes. Returns stripped text or None."""
        if not pcm_bytes:
            return None
        try:
            self._load()
        except Exception:
            return None

        import numpy as np  # type: ignore[import]

        n_samples = len(pcm_bytes) // 2
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Resample if needed (unlikely since Pi captures at 16kHz)
        if sample_rate != SAMPLE_RATE:
            import resampy  # type: ignore[import]
            audio = resampy.resample(audio, sample_rate, SAMPLE_RATE)

        try:
            segments, _ = self._model.transcribe(
                audio,
                language="en",
                beam_size=1,
                best_of=1,
                temperature=0,
                vad_filter=False,  # we already do VAD upstream
            )
            text = " ".join(s.text for s in segments).strip()
            return text if text else None
        except Exception as exc:
            log.warning("transcriber: transcription failed: %s", exc)
            return None
