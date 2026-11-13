"""Fail-closed tests for ECO-002 real joined ingress-to-ledger timing artifacts."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "eco002_ingress_ledger_latency_report",
    ROOT / "scripts" / "eco002_ingress_ledger_latency_report.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def log(surface, outcome, *, ingress=2, verified=3):
    tail = f" verified_ms={verified}" if outcome == "completed" else ""
    return (
        f"eco002_ingress_ledger surface={surface} outcome={outcome} "
        f"provenance=isolated_receiver samples=1 ingress_ms={ingress}{tail}"
    )


def test_two_joined_surfaces_and_replays_produce_only_diagnostic_evidence():
    result = module.summarize([
        log("chat", "completed"), log("chat", "replay"),
        log("agent", "completed"), log("agent", "replay"),
    ])
    assert result["complete"]
    assert not result["eligible_for_optimization"]
    assert result["classification"] == "diagnostic_single_sample_not_p50_p95"
    assert result["observations"]["chat/completed"]["verified_ms"] == 3


def test_missing_surface_rejected():
    report = module.summarize([log("chat", "completed")])
    assert not report["complete"]
    assert "agent/completed" in report["missing"]


def test_duplicate_and_unverified_terminal_evidence_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        module.summarize([log("chat", "completed")] * 2)
    with pytest.raises(ValueError, match="verification"):
        module.summarize([log("agent", "completed", ingress=4, verified=3)])
    with pytest.raises(ValueError, match="verification"):
        module.summarize([
            "eco002_ingress_ledger surface=chat outcome=completed "
            "provenance=isolated_receiver samples=1 ingress_ms=2"
        ])
