import logging
from functools import lru_cache

from app.config import settings
from app.pipeline.fixtures import LARP_TEXT, TRUTHFUL_TEXT

log = logging.getLogger(__name__)


def transcribe_fixture_frame(frame_index: int, audio: bytes) -> str:
    """Deterministic ASR stand-in until faster-whisper is wired to real WAV/audio frames."""
    if frame_index == 1:
        return TRUTHFUL_TEXT
    if frame_index == 2:
        return LARP_TEXT
    return ""


@lru_cache(maxsize=1)
def whisper_model():
    from faster_whisper import WhisperModel

    device = settings.whisper_device
    compute_type = settings.whisper_compute_type
    if device == "auto":
        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
    if compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"
    log.info("asr: loading faster-whisper model=%s device=%s compute_type=%s", settings.whisper_model, device, compute_type)
    return WhisperModel(settings.whisper_model, device=device, compute_type=compute_type)


def transcribe_pcm_frame(audio: bytes, sample_rate: int = 16000) -> str:
    """Transcribe raw mono PCM s16le audio sent by the Pi or browser capture client."""
    if not audio:
        return ""
    try:
        import numpy as np

        pcm = np.frombuffer(audio, dtype=np.int16)
        if pcm.size < sample_rate // 2:
            return ""
        samples = pcm.astype(np.float32) / 32768.0
        segments, _ = whisper_model().transcribe(
            samples,
            language="en",
            vad_filter=True,
            beam_size=1,
            best_of=1,
            condition_on_previous_text=False,
            no_speech_threshold=0.45,
            temperature=0.0,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return text if len(text) >= 3 else ""
    except Exception as exc:
        # Do not emit fake claims when real ASR is unavailable or still warming up.
        log.warning("asr: transcription failed: %s", exc)
        return ""
