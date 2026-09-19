"""3.0-A critical-path latency analyzer — dominant stage, not averages."""
from __future__ import annotations

from app.services.turn_latency_trace import analyze_cumulative_checkpoints, map_stage


def test_dominant_stage_is_largest_delta_not_last_mark() -> None:
    analysis = analyze_cumulative_checkpoints(
        {
            "client_ready": 20,
            "resolution": 80,
            "context_compile": 900,
            "compose": 950,
        }
    )
    assert analysis["dominant_stage"] == "CONTEXT_BUILD"
    assert analysis["dominant_checkpoint"] == "context_compile"
    assert analysis["dominant_ms"] == 820
    assert analysis["total_ms"] == 950
    assert map_stage("react") == "MODEL_TTFT"


def test_empty_marks_are_unknown() -> None:
    analysis = analyze_cumulative_checkpoints({})
    assert analysis["dominant_stage"] == "UNKNOWN"
    assert analysis["total_ms"] == 0
