def compute_score(flags: list[dict]) -> float:
    return min(1.0, sum(flag.get("score_delta", 0.0) for flag in flags))


def score_label(score: float) -> str:
    if score < 0.25:
        return "mostly honest"
    if score < 0.6:
        return "approaching freestyle"
    return "full improv mode"
