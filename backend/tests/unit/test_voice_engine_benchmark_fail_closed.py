"""Guard against mistaking aggregate voice metrics for live certification."""
from app.services.pipecat_voice.engine_benchmark import VoiceTrial, compare_engines


def test_aggregate_voice_metrics_cannot_certify_live_adapter():
    rows = [VoiceTrial(engine, 100 if engine == "duplex" else 50, 100, 100, True, 0.1)
            for engine in ("duplex", "pipecat", "livekit") for _ in range(20)]
    result = compare_engines(rows)
    assert result["sample_counts_sufficient"]
    assert not result["evidence_sufficient"]
    assert not result["recommend_pipecat"]
    assert not result["recommend_livekit"]
    assert result["default_engine"] == "duplex"


def test_cancelled_write_is_unsafe():
    rows = [VoiceTrial(engine, 100, 100, 100, True, 0.1, cancelled_write_executed=(engine == "pipecat"))
            for engine in ("duplex", "pipecat", "livekit") for _ in range(20)]
    result = compare_engines(rows)
    assert not result["safety_passed"]
    assert result["engines"]["pipecat"]["cancelled_write_violations"] == 20
    assert not result["recommend_pipecat"]
