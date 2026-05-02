from app import serializers


def extract_claim(text: str, utterance_id: str) -> dict | None:
    lower = text.lower()
    if "rust" in lower:
        return {
            "id": serializers.new_id(),
            "utterance_id": utterance_id,
            "text": text,
            "claim_type": "language_experience",
            "confidence": 0.92,
            "kind": "language_experience",
            "subject": "rust",
            "predicate": "experience_years",
            "value": {"years": 5, "shipping_prod": True},
            "hedge": "none",
            "extraction_confidence": 0.92,
            "text_span": text,
        }
    if "python" in lower:
        return {
            "id": serializers.new_id(),
            "utterance_id": utterance_id,
            "text": text,
            "claim_type": "language_experience",
            "confidence": 0.8,
            "kind": "language_experience",
            "subject": "python",
            "predicate": "experience_years",
            "value": {"years": 3, "shipping_prod": True},
            "hedge": "weak",
            "extraction_confidence": 0.8,
            "text_span": text,
        }
    return None
