"""Verify dedicated manual acceptance entrypoints and keep target restrictions immutable."""
from pathlib import Path
import re
import subprocess
import sys
import textwrap

import pytest

ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"


@pytest.mark.parametrize("override, expected, diagnostic", [
    ({}, 0, None),
    ({"E2E_STRIPE_SECRET_KEY": "sk_live_synthetic_forbidden"}, 1, "stripe_test_mode_key"),
    ({"E2E_SUPABASE_URL": "https://production.invalid"}, 1, "dedicated_supabase_target"),
    ({"E2E_SUPABASE_ALLOWED_URL": "https://other.invalid"}, 1, "allowed_url_matches_target"),
    ({"E2E_SUPABASE_URL": "https://aadnwmjzrmbvadszroqt.supabase.co?x=1"}, 1, "undecorated_https_target"),
    ({"E2E_SUPABASE_SERVICE_ROLE_KEY": ""}, 1, "E2E_SUPABASE_SERVICE_ROLE_KEY"),
])
def test_actual_billing_credential_guard_executes_and_fails_closed(override, expected, diagnostic):
    workflow = (ROOT / "isolated-acceptance.yml").read_text()
    block = re.search(r"(?ms)^          python - <<'PY'\n(.*?)^          PY$", workflow)
    assert block, "Billing credential guard must exist before fixture seeding"
    source = textwrap.dedent(block.group(1))
    compile(source, "billing-credential-guard", "exec")
    env = {
        "E2E_SUPABASE_URL": "https://aadnwmjzrmbvadszroqt.supabase.co",
        "E2E_SUPABASE_ALLOWED_URL": "https://aadnwmjzrmbvadszroqt.supabase.co",
        "E2E_STRIPE_SECRET_KEY": "sk_test_synthetic_no_provider_calls",
        "E2E_STRIPE_PRICE_ID_NODE_MONTHLY": "price_synthetic",
        "E2E_SUPABASE_ANON_KEY": "synthetic-anon",
        "E2E_SUPABASE_SERVICE_ROLE_KEY": "synthetic-service",
        "E2E_SUPABASE_JWT_SECRET": "synthetic-jwt",
        **override,
    }
    result = subprocess.run([sys.executable, "-c", source], env=env,
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == expected, result.stderr
    if diagnostic:
        assert diagnostic in result.stderr
    assert not any(value in result.stdout + result.stderr for value in env.values() if value)


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
