"""ECO-003 measured-log reporting contracts."""
import importlib.util
from pathlib import Path
import pytest

PATH = Path(__file__).resolve().parents[2] / "scripts/eco003_context_latency_report.py"
spec = importlib.util.spec_from_file_location("eco003_context_latency_report", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_scenarios_are_separated_and_ranked_from_emitted_timings():
    lines = [
        "eco003_context_stage_timing retrieval_ms=20 company_ms=10 research_ms=0 total_ms=35 retrieval_ok=True research_requested=False",
        "eco003_context_stage_timing retrieval_ms=30 company_ms=15 research_ms=50 total_ms=100 retrieval_ok=True research_requested=True",
    ]
    result = module.summarize(lines, provenance="verified_nonproduction")
    assert result["scenarios"]["no_research"]["stages"]["retrieval"]["p95_ms"] == 20
    assert result["scenarios"]["research"]["stages"]["research"]["p95_ms"] == 50
    assert result["scenarios"]["research"]["samples"] == 1


def test_rejects_fixture_provenance_and_empty_logs():
    with pytest.raises(ValueError, match="provenance"):
        module.summarize([], provenance="fixture")
    with pytest.raises(ValueError, match="no emitted"):
        module.summarize([], provenance="verified_nonproduction")


def test_acceptance_report_requires_sufficient_samples_per_scenario():
    lines = [
        "eco003_context_stage_timing retrieval_ms=20 company_ms=10 research_ms=0 total_ms=35 retrieval_ok=True research_requested=False",
        "eco003_context_stage_timing retrieval_ms=30 company_ms=15 research_ms=50 total_ms=100 retrieval_ok=True research_requested=True",
    ]
    with pytest.raises(ValueError, match="insufficient observations for"):
        module.summarize(lines, provenance="verified_nonproduction", min_samples=2)
    assert module.summarize(lines[:1] * 2, provenance="verified_nonproduction", min_samples=2)["scenarios"]["no_research"]["samples"] == 2
    with pytest.raises(ValueError, match="min_samples"):
        module.summarize(lines, provenance="verified_nonproduction", min_samples=0)
