"""Trusted autonomous write authority: fresh run checks and fail-closed decisions."""
from types import SimpleNamespace
from unittest.mock import patch

from app.operators.react_engine import ReActEngine


def _ctx(run_id="run-1", org_id="tenant-1"):
    return SimpleNamespace(client=object(), org_id=org_id, run_id=run_id)


def test_run_approval_uses_canonical_fresh_approval_lookup():
    ctx = _ctx()
    with patch("app.services.canvas_write_gate.require_approved_authority_run", return_value={"id": "run-1"}) as check:
        assert ReActEngine._approved_autonomous_run(ctx) is True
        check.assert_called_once_with(
            client=ctx.client, org_id="tenant-1", run_id="run-1", authority_ref="run-1",
        )


def test_missing_revoked_and_wrong_tenant_run_fail_closed():
    for ctx in (_ctx(None), _ctx(org_id="other-tenant")):
        with patch("app.services.canvas_write_gate.require_approved_authority_run", side_effect=ValueError("not approved")):
            assert ReActEngine._approved_autonomous_run(ctx) is False
