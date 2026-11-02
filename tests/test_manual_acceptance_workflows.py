"""Verify dedicated manual acceptance entrypoints and keep target restrictions immutable."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def test_manual_billing_entrypoint_uses_shared_verified_suite():
    workflow = (ROOT / "run-acceptance-billing.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "uses: ./.github/workflows/isolated-acceptance.yml" in workflow
    assert "suite: billing" in workflow
    assert "secrets: inherit" in workflow


def test_manual_voice_entrypoint_uses_shared_verified_suite():
    workflow = (ROOT / "run-acceptance-voice.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "uses: ./.github/workflows/isolated-acceptance.yml" in workflow
    assert "suite: voice" in workflow
    assert "secrets: inherit" in workflow


def test_reusable_suite_target_and_provider_contracts():
    workflow = (ROOT / "isolated-acceptance.yml").read_text()
    assert "workflow_call:" in workflow
    assert "inputs.suite == 'billing'" in workflow
    assert "inputs.suite == 'voice'" in workflow
    assert "https://aadnwmjzrmbvadszroqt.supabase.co" in workflow
    assert "scripts/check-isolated-acceptance-db.py" in workflow
    assert "E2E_STRIPE_SECRET_KEY" in workflow
    assert "scripts/verify-voice-provider-roundtrip.py" in workflow
    assert "environment: acceptance" in workflow


def test_database_preparation_is_explicitly_read_only():
    workflow = (ROOT / "acceptance-db-preflight.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "scripts/prepare_acceptance_baseline.py" in workflow
    assert "scripts/check_acceptance_remote_readonly.py" in workflow
    assert "supabase db push" not in workflow
    assert "psql " not in workflow


def test_generated_quality_stays_manual_and_checks_actual_production_revision():
    workflow = (ROOT / "live-generated-response-quality.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert 'https://api.gravitre.app/health' in workflow
    assert 'health.get("git_sha") != os.environ["DEPLOYED_SHA"]' in workflow
    assert "environment: production-evaluation" in workflow
