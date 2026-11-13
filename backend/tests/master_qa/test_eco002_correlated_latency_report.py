"""ECO-002 correlated latency evidence acceptance."""
import importlib
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
summarize = importlib.import_module('eco002_correlated_latency_report').summarize


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


def test_orphaned_stage_samples_do_not_count_as_correlated_requests():
    lines = [
        "router_stage_timing stage=knowledge_response surface=chat outcome=ok duration_ms=3 sample=knowledge-0001",
        "eco002_request_wall scenario=knowledge sample=knowledge-0001 duration_ms=9",
        "router_stage_timing stage=model_provider surface=chat outcome=ok duration_ms=7 sample=unpaired-0002",
    ]
    report = summarize(lines)
    assert report["request_count"] == 1
    assert report["orphan_stage_sample_count"] == 1
    assert not report["correlation_complete"]
    assert "knowledge/model_provider" not in report["boundaries"]


def test_stage_errors_remain_visible_without_becoming_success_samples():
    lines = [
        "router_stage_timing stage=execution surface=chat outcome=error duration_ms=3 sample=governed_action-0001",
        "eco002_request_wall scenario=governed_action sample=governed_action-0001 duration_ms=9",
    ]
    report = summarize(lines)
    assert report["correlation_complete"]
    assert report["failed_request_count"] == 1
    assert "governed_action/execution" not in report["boundaries"]


def test_missing_stages_fail_correlation():
    report = summarize(["eco002_request_wall scenario=knowledge sample=knowledge-0001 duration_ms=9"])
    assert report["unmatched_request_count"] == 1
    assert not report["correlation_complete"]


def test_correlated_request_shape_buckets_are_required_only_for_shape_gate():
    lines = [
        "eco002_request_shape sample=knowledge-0001 surface=chat request_bytes_bucket=1_128 history_count_bucket=zero",
        "router_stage_timing stage=knowledge_response surface=chat outcome=ok duration_ms=3 sample=knowledge-0001",
        "eco002_request_wall scenario=knowledge sample=knowledge-0001 duration_ms=9",
    ]
    report = summarize(lines, require_shapes=True)
    assert report["correlation_complete"]
    assert report["shape_coverage_count"] == 1
    assert report["request_shape_buckets"]["knowledge"]["chat/1_128/zero"] == 1
    assert not summarize(lines[1:], require_shapes=True)["correlation_complete"]


def test_duplicate_or_orphan_shape_fails_closed():
    shape = "eco002_request_shape sample=knowledge-0001 surface=chat request_bytes_bucket=1_128 history_count_bucket=zero"
    base = [
        shape,
        "router_stage_timing stage=knowledge_response surface=chat outcome=ok duration_ms=3 sample=knowledge-0001",
        "eco002_request_wall scenario=knowledge sample=knowledge-0001 duration_ms=9",
    ]
    duplicated = summarize([shape, *base], require_shapes=True)
    assert duplicated["duplicate_shape_count"] == 1
    assert not duplicated["correlation_complete"]
    orphaned = summarize([*base, shape.replace("knowledge-0001", "unpaired-0002")], require_shapes=True)
    assert orphaned["orphan_shape_count"] == 1
    assert not orphaned["correlation_complete"]
