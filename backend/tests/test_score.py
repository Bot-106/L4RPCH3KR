from app.pipeline.score import _parse_score_json


def test_parse_score_json_accepts_markdown_fence() -> None:
    assert _parse_score_json('```json\n{"score": 0.72}\n```') == {"score": 0.72}


def test_parse_score_json_extracts_embedded_json() -> None:
    assert _parse_score_json('Here is the score: {"score": 0.45}') == {"score": 0.45}
