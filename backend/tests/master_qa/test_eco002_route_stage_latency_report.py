"""ECO-002 actual-emitted-stage log aggregation without invented baselines."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/eco002_route_stage_latency_report.py"
spec = importlib.util.spec_from_file_location("eco002_route_stage_latency_report", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_real_stage_logs_preserve_count_errors_and_percentiles():
    logs = [
        "eco002_route_stage stage=response_dispatch outcome=ok duration_ms=10.000",
        "eco002_route_stage stage=response_dispatch outcome=ok duration_ms=30.000",
        "eco002_route_stage stage=response_dispatch outcome=error duration_ms=3.000",
        "eco002_route_stage stage=model_selection outcome=ok duration_ms=7.000",
    ]
    report = module.summarize(logs, provenance="verified_nonproduction", min_samples=1)
    assert report["stage_summaries"]["response_dispatch"] == {
        "samples": 2, "errors": 1, "p50_ms": 20, "p95_ms": 29
    }
    assert report["stage_summaries"]["model_selection"]["p95_ms"] == 7
    assert report["eligible_for_optimization"] is False


@pytest.mark.parametrize("records,provenance,samples", [
    ([], "fixture", 1),
    ([], "verified_nonproduction", 1),
    (["eco002_route_stage stage=classification outcome=ok duration_ms=1.000"], "verified_nonproduction", 30),
    (["eco002_route_stage stage=tenant_123 outcome=ok duration_ms=1.000"], "verified_nonproduction", 1),
    (["eco002_route_stage stage=classification outcome=ok duration_ms=nan"], "verified_nonproduction", 1),
])
def test_bad_provenance_empty_insufficient_and_unknown_stage_fail_closed(records, provenance, samples):
    with pytest.raises(ValueError):
        module.summarize(records, provenance=provenance, min_samples=samples)


def test_stage_samples_are_not_claimed_to_be_complete_request_traces():
    report = module.summarize([
        "eco002_route_stage stage=classification outcome=ok duration_ms=4.000"
    ], provenance="verified_nonproduction", min_samples=1)
    assert "stage_summaries" in report
    assert "request_count" not in report
    assert report["eligible_for_optimization"] is False


@pytest.mark.parametrize("record", [
    "stage=classification outcome=ok duration_ms=-3.000",
    "stage=classification outcome=ok duration_ms=nan",
    "stage=classification outcome=ok duration_ms=inf",
    "stage=classification outcome=ok duration_ms=3.0garbage",
    "stage=classification outcome=ok duration_ms=3.0.1",
    "stage=classification outcome=unknown duration_ms=3.000",
    "stage=classification outcome=ok duration_ms=",
    "stage=classification duration_ms=3.000",
])
def test_malformed_timing_cannot_hide_among_valid_samples(record):
    with pytest.raises(ValueError, match="malformed ECO-002"):
        module.summarize([
            "eco002_route_stage stage=classification outcome=ok duration_ms=5.000",
            "eco002_route_stage " + record,
        ], provenance="verified_nonproduction", min_samples=1)


def test_unrelated_logs_and_structured_log_suffix_do_not_drop_valid_samples():
    report = module.summarize([
        "INFO unrelated operation completed",
        "INFO eco002_route_stage stage=classification outcome=ok duration_ms=0.000 logger=router",
        "INFO eco002_route_stage stage=classification outcome=ok duration_ms=8.000",
    ], provenance="verified_nonproduction", min_samples=2)
    assert report["stage_summaries"]["classification"] == {
        "samples": 2, "errors": 0, "p50_ms": 4, "p95_ms": 7.6,
    }


def test_json_formatter_records_parse_message_without_exporting_identity_fields():
    report = module.summarize([json.dumps({
        "message": "eco002_route_stage stage=classification outcome=ok duration_ms=5.000",
        "org_id": "private-tenant",
        "request_id": "private-request",
    })], provenance="verified_nonproduction", min_samples=1)
    assert report["stage_summaries"]["classification"]["p95_ms"] == 5
    assert "private-tenant" not in json.dumps(report)
    assert "private-request" not in json.dumps(report)


def test_malformed_json_timing_record_cannot_count_as_valid_sample():
    with pytest.raises(ValueError, match="malformed ECO-002 JSON"):
        module.summarize([
            '{"message": "eco002_route_stage stage=classification outcome=ok duration_ms=5.000"',
        ], provenance="verified_nonproduction", min_samples=1)


def test_model_provider_stage_is_reported_without_request_payloads():
    report = module.summarize([
        "eco002_route_stage stage=model_provider outcome=ok duration_ms=12.000",
        "eco002_route_stage stage=model_provider outcome=ok duration_ms=16.000",
    ], provenance="verified_nonproduction", min_samples=2)
    assert report["stage_summaries"]["model_provider"]["p50_ms"] == 14
    assert report["stage_summaries"]["model_provider"]["p95_ms"] == 15.8
    assert report["eligible_for_optimization"] is False
