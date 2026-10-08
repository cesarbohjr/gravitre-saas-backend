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


def test_aggregate_reports_percentiles_only_with_enough_samples() -> None:
    from app.services.turn_latency_trace import aggregate_stage_percentiles

    rows = [
        {"tier": "light", "stage_durations_ms": {"model_ttft_ms": ms, "tts_ttfb_ms": 150}}
        for ms in range(1, 21)
    ] + [{"tier": "deep", "stage_durations_ms": {"model_ttft_ms": 900}}] * 3
    rows.append({"no": "durations"})
    out = aggregate_stage_percentiles(rows)
    light = out["light"]["model_ttft_ms"]
    assert light == {"n": 20, "p50": 10, "p95": 19, "p99": None}
    # Three samples is not enough for any percentile.
    assert out["deep"]["model_ttft_ms"] == {"n": 3, "p50": None, "p95": None, "p99": None}
    assert out["all"]["model_ttft_ms"]["n"] == 23
    assert out["light"]["tts_ttfb_ms"]["p95"] == 150


def test_aggregate_p99_needs_one_hundred_samples() -> None:
    from app.services.turn_latency_trace import aggregate_stage_percentiles

    rows = [{"stage_durations_ms": {"x": float(i)}} for i in range(1, 101)]
    out = aggregate_stage_percentiles(rows)
    assert out["unknown"]["x"]["p99"] == 99
    assert out["unknown"]["x"]["p50"] == 50


def test_voice_critical_path_carries_tier_and_durations(monkeypatch) -> None:
    from app.services import turn_latency_trace

    captured: dict = {}

    def _write(_client, org_id, user_id, action, resource_type, resource_id, payload):
        captured.update(payload)

    monkeypatch.setattr("app.workflows.audit.write_audit_event", _write)
    monkeypatch.setattr("app.workflows.repository.get_supabase_client", lambda _s: object())
    analysis = turn_latency_trace.record_voice_turn_critical_path(
        None,
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
        conversation_id=None,
        turn_id="t-1",
        marks={"client_ready": 0, "turn_committed": 400, "llm_first_token_ms": 1200},
        transport="pipecat_duplex",
        tier="light",
        stage_durations_ms={"eot_detection_ms": 400, "model_ttft_ms": None},
        extra={"speculative_outcome": "adopted"},
    )
    assert captured["tier"] == "light"
    assert captured["stage_durations_ms"] == {"eot_detection_ms": 400}
    assert captured["speculative_outcome"] == "adopted"
    assert analysis["dominant_checkpoint"] == "llm_first_token_ms"
