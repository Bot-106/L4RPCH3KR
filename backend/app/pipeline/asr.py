from app.pipeline.fixtures import LARP_TEXT, TRUTHFUL_TEXT


def transcribe_fixture_frame(frame_index: int, audio: bytes) -> str:
    """Deterministic ASR stand-in until faster-whisper is wired to real WAV/audio frames."""
    if frame_index == 1:
        return TRUTHFUL_TEXT
    if frame_index == 2:
        return LARP_TEXT
    return ""
