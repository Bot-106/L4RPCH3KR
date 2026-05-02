def classify_speaker(speaker_hint: str | None = None) -> tuple[str, float]:
    if speaker_hint == "subject":
        return "subject", 0.87
    if speaker_hint in {"self", "partner", "unknown"}:
        confidence = 0.95 if speaker_hint == "self" else 0.87 if speaker_hint == "partner" else 0.5
        return speaker_hint, confidence
    return "subject", 0.87
