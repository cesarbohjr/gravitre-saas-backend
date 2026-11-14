"""Fail closed on regressions to the canonical master QA workflow inventory.

This is a source contract only. Live required status checks, production costs and
GitHub Actions permissions require separate owner-authorized verification.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github" / "workflows"


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text()


def test_one_canonical_master_gate_with_full_qa_lane_contract():
    master = workflow("master-qa-p0-synthetic.yml")
    assert master.startswith("name: Master QA | QA00–QA90 Core Evidence & Runtime\n")
    assert "master_qa_remediation_guard.py" in master
    assert "master_qa_release_certifier.py" in master
    assert "master_qa_wiring_preflight.py" in master
    assert "test_real_guard_postgres_consumer_pg.py" in master
    for test in (
        "test_eco002_route_stage_metrics.py",
        "test_eco003_context_stage_metrics.py",
        "test_eco003_context_scope_parity.py",
    ):
        assert test in master


def test_required_specialist_coverage_and_manual_live_approval_are_retained():
    for name in (
        "ci.yml",
        "master-qa-p0-synthetic.yml",
        "master-qa-p27-sandbox-readback.yml",
        "eco-001-deployed-ingress.yml",
        "supabase-migration-safety.yml",
        "connector-governance.yml",
        "outcome-ownership-contract.yml",
        "autonomous-write-certification.yml",
        "voice-gates-2-3.yml",
        "voice-duplex-guard.yml",
        "department-eval-suites.yml",
        "phase3-offline-12-scenarios.yml",
        "production-release-verification.yml",
    ):
        assert (WORKFLOWS / name).is_file(), name
    authorized = workflow("master-qa-p27-sandbox-readback.yml")
    assert "workflow_dispatch:" in authorized
    assert "APPROVE_LIVE_TEST_CONTACT" in authorized
    ingress = workflow("eco-001-deployed-ingress.yml")
    assert "workflow_dispatch:" in ingress
    assert "eco001_deployed_ingress_preflight.py" in ingress
    assert "pull_request:" not in ingress


def test_obsolete_write_capable_branch_reconcile_not_reintroduced():
    assert not (WORKFLOWS / "pr587-controlled-reconcile.yml").exists()


def test_full_ci_preserves_comprehensive_backend_and_web_jobs():
    ci = workflow("ci.yml")
    assert "  backend:" in ci
    assert "  web:" in ci
    assert "  mcp-crash-acceptance:" in ci
