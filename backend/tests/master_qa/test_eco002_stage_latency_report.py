"""Offline, dependency-free regression of correlated ECO-002 report aggregation."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "eco002_stage_latency_report.py"
spec = importlib.util.spec_from_file_location("eco002_stage_latency_report", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_correlated_samples_are_grouped_and_ranked():
    lines = [
        "router_stage_timing stage=classification surface=chat outcome=ok duration_ms=10.000 sample=ci-1",
        "router_stage_timing stage=context surface=chat outcome=ok duration_ms=30.000 sample=ci-1",
        "router_stage_timing stage=classification surface=chat outcome=ok duration_ms=20.000 sample=ci-2",
        "router_stage_timing stage=context surface=chat outcome=ok duration_ms=80.000 sample=ci-2",
        "router_stage_timing stage=context surface=chat outcome=error duration_ms=100.000 sample=ci-3",
    ]
    report = module.summarize(lines)
    assert report["sample_count"] == 4
    assert report["correlated_trace_count"] == 2
    assert report["ranked_by_stage_p95"][0]["stage"] == "context"
    assert report["ranked_observed_stage_share"][0]["stage"] == "context"
    assert report["correlated_traces"][0]["observed_stage_sum_ms"] == 40.0
    assert report["correlated_traces"][1]["observed_stage_sum_ms"] == 100.0
    assert report["ranked_by_stage_p95"][0]["errors"] == 1


def test_uncorrelated_lines_do_not_create_fake_traces():
    report = module.summarize([
        "router_stage_timing stage=context surface=chat outcome=ok duration_ms=2.500"
    ])
    assert report["sample_count"] == 1
    assert report["correlated_trace_count"] == 0
