"""ECO-002 correlated latency evidence acceptance."""
import pytest
from scripts.eco002_correlated_latency_report import summarize


def test_fixture_correlation_never_authorizes_optimization():
    lines = [
        "router_stage_timing stage=knowledge_response surface=chat outcome=ok duration_ms=3.000 sample=knowledge-0001",
        "eco002_request_wall scenario=knowledge sample=knowledge-0001 duration_ms=9.000",
    ]
    report = summarize(lines)
    assert report["scenarios"]["knowledge"]["p95_ms"] == 9
    assert report["boundaries"]["knowledge/knowledge_response"]["p50_ms"] == 3
    assert not report["eligible_for_optimization"]
    assert not report["model_provider_observed"]


def test_duplicate_wall_sample_is_rejected():
    lines = ["eco002_request_wall scenario=knowledge sample=a duration_ms=1"] * 2
    with pytest.raises(ValueError, match="duplicate"):
        summarize(lines)


def test_real_model_and_execution_still_require_verified_provenance():
    lines = [
        "router_stage_timing stage=model_provider surface=chat outcome=ok duration_ms=30 sample=governed_action-0001",
        "router_stage_timing stage=execution surface=chat outcome=ok duration_ms=50 sample=governed_action-0001",
        "eco002_request_wall scenario=governed_action sample=governed_action-0001 duration_ms=100",
    ]
    assert not summarize(lines)["eligible_for_optimization"]
    assert not summarize(lines, provenance="verified_nonproduction")["eligible_for_optimization"]
    assert not summarize(lines, provenance="verified_nonproduction")["actual_external_provider_observed"]
