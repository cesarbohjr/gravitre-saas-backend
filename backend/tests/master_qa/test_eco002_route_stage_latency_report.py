"""ECO-002 actual-emitted-stage log aggregation without invented baselines."""
from __future__ import annotations

import importlib.util
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
