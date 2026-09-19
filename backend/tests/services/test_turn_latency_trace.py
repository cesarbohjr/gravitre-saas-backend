"""3.0-A critical-path latency analyzer — dominant stage, not averages."""
from __future__ import annotations

from app.services.turn_latency_trace import (
    analyze_cumulative_checkpoints,
    build_voice_http_turn_marks,
    build_voice_pipecat_turn_marks,
    map_stage,
)


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


def test_build_voice_http_turn_marks_maps_ttfa_and_terminal() -> None:
    marks = build_voice_http_turn_marks(
        completion_ms=5000,
        first_text_ms=400,
        first_audio_ms=900,
        classify_done_ms=120,
    )
    analysis = analyze_cumulative_checkpoints(marks)
    assert marks["tts_first_byte"] == 900
    assert analysis["total_ms"] == 5000
    assert map_stage("tts_first_byte") == "TTS_BUFFER"


def test_build_voice_pipecat_turn_marks_maps_processors() -> None:
    marks = build_voice_pipecat_turn_marks(
        end_to_end_ms=4200,
        user_turn_finalization_ms=800,
        ttfb_by_processor_ms={
            "GravitreCognitiveLLMService": 650,
            "ElevenLabsTTSService": 180,
        },
    )
    assert marks["llm_first_token_ms"] == 650
    assert marks["tts_first_byte"] == 180
    assert marks["terminal"] == 4200
