"""ECO-003: canonical nonproduction measurement report contracts."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / "scripts/eco003_context_latency_report.py"
spec = importlib.util.spec_from_file_location("eco003_context_latency_report", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample(stage: str, ms: float, outcome: str = "ok") -> str:
    return f"eco003_context_stage stage={stage} outcome={outcome} duration_ms={ms:.3f}"


def test_report_uses_existing_canonical_stage_spans_only():
    lines = [sample("unified_retrieval", i) for i in range(1, 31)]
    lines += [sample("context_assembly_total", i * 2) for i in range(1, 31)]
    lines += [sample("unified_retrieval", 80, "error")]
    result = module.summarize(lines, provenance="verified_nonproduction")
    assert result["status"] == "measured_nonproduction_only_not_qa_certified"
    retrieval = result["stage_statistics"]["unified_retrieval"]
    assert retrieval["successful_samples"] == 30 and retrieval["failed_samples"] == 1
    assert retrieval["p50_ms"] == 15.5
    assert retrieval["p95_ms"] == 28.55
    assert result["stage_statistics"]["context_assembly_total"]["p95_ms"] == 57.1


def test_untrusted_source_or_insufficient_observations_cannot_report():
    with pytest.raises(ValueError, match="provenance"):
        module.summarize([sample("org_context", 1)] * 30, provenance="fixture")
    with pytest.raises(ValueError, match="no canonical"):
        module.summarize([], provenance="verified_nonproduction")
    with pytest.raises(ValueError, match="insufficient"):
        module.summarize([sample("org_context", 1)] * 29, provenance="verified_nonproduction")
    with pytest.raises(ValueError, match="min_samples"):
        module.summarize([sample("org_context", 1)] * 30,
                         provenance="verified_nonproduction", min_samples=1)


def test_rejects_unknown_stage_and_does_not_report_labels():
    with pytest.raises(ValueError, match="unknown static"):
        module.summarize([sample("tenant_secret", 1)] * 30,
                         provenance="verified_nonproduction")
    result = module.summarize(
        [sample("agent_memory", 10)] * 30,
        provenance="verified_nonproduction",
    )
    assert list(result["stage_statistics"]) == ["agent_memory"]
    assert "tenant_secret" not in str(result)
