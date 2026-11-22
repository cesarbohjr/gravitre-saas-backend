"""Fail closed on regressions to the canonical master QA workflow inventory.

This is a source contract only. Live required status checks, production costs and
GitHub Actions permissions require separate owner-authorized verification.
"""
from __future__ import annotations

from pathlib import Path
from runpy import run_path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github" / "workflows"
source_contract = run_path(str(ROOT / 'scripts/workflow_source_contract.py'))


def workflow(name: str) -> str:
    return source_contract['text'](ROOT, name)


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
        "master-qa-qa30-acoustic-qualification.yml",
        "master-qa-qa30-offline-cancellation.yml",
        "master-qa-qa30-voice-confirmed-turns.yml",
        "voice-duplex-guard.yml",
        "department-eval-suites.yml",
        "phase3-offline-12-scenarios.yml",
        "production-release-verification.yml",
    ):
        assert source_contract['definition'](ROOT, name)['jobs'], name
    authorized = workflow("master-qa-p27-sandbox-readback.yml")
    assert "workflow_dispatch:" in authorized
    assert "APPROVE_LIVE_TEST_CONTACT" in authorized
    ingress = workflow("eco-001-deployed-ingress.yml")
    assert "workflow_dispatch:" in ingress
    assert "eco001_deployed_ingress_preflight.py" in ingress
    # PRs run main's offline fixture contracts; credentialed jobs stay manual.
    assert "pull_request:" in ingress
    assert "tests/test_eco001_disposable_preflight.py" in ingress


def test_obsolete_write_capable_branch_reconcile_not_reintroduced():
    for legacy in (
        "pr587-controlled-reconcile.yml",
        "pr587-local-acoustic.yml",
        "pr587-offline-cancellation.yml",
        "issue-535-voice-confirmation.yml",
    ):
        assert not (WORKFLOWS / legacy).exists(), legacy
    assert "pr587_offline_cancel_gate.py" in workflow("master-qa-qa30-offline-cancellation.yml")
    assert "pr587_kws_qualification.py" in workflow("master-qa-qa30-acoustic-qualification.yml")
    assert "test_phase3_provider_commit_gate.py" in workflow("master-qa-qa30-voice-confirmed-turns.yml")


def test_signed_qa_ingress_uses_only_the_owner_dispatched_isolated_environment():
    jobs = source_contract['definition'](ROOT, 'eco-001-deployed-ingress.yml')['jobs']
    offline = jobs['fixture-contracts']
    authorize = jobs['authorize']
    signed = jobs['signed-qa-ingress-preflight']
    assert 'environment' not in offline
    assert 'secrets.' not in str(offline)
    assert signed['environment'] == 'acceptance'
    assert signed['permissions'] == {'contents': 'read'}
    assert "github.event_name == 'workflow_dispatch'" in signed['if']
    assert "github.event_name == 'workflow_dispatch'" in authorize['if']
    guard = authorize['steps'][0]
    assert 'test "$ACTOR" = cesarbohjr' in guard['run']
    assert 'test "$DISPATCH_REF" = refs/heads/main' in guard['run']
    assert 'test "$CONFIRM_DISPOSABLE_FIXTURE" = true' in guard['run']
    assert signed['env']['QA_BACKEND_URL'] == 'https://eco001-fastapi-qa.up.railway.app'
    assert any('authorize' in dependency for dependency in signed['needs'])
    assert any('fixture-contracts' in dependency for dependency in signed['needs'])
    assert signed['steps'][0]['with']['persist-credentials'] is False
    assert 'ECO001_QA_BEARER' not in str(signed)
    assert 'E2E_SUPABASE_SERVICE_ROLE_KEY' in str(signed)
    cleanup, upload = signed['steps'][-2:]
    assert cleanup['if'] == upload['if'] == 'always()'
    assert '--cleanup-only' in cleanup['run']
    assert upload['with']['path'].endswith('/eco001-signed-qa-ingress.json')


def test_full_ci_preserves_comprehensive_backend_and_web_jobs():
    ci = workflow("ci.yml")
    assert "  backend:" in ci
    assert "  web:" in ci
    assert "  mcp-crash-acceptance:" in ci
