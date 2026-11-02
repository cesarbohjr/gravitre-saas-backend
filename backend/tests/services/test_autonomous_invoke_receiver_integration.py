"""Exercise production invoke_tool with an independent process side-effect receiver.

This is a real invoke spine test with a simulated approval ledger. The separate
PostgreSQL suite certifies the atomic RPC. It is NOT worker SIGKILL certification.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import json
import urllib.request

import pytest

from app.services import tool_service
from app.services.tool_types import NormalizedResult, ToolContext
from app.services.write_authority import write_authority
from app.services.write_invoke_idempotency import WriteClaimResult
from tests.db.test_autonomous_independent_write_pg import IndependentFixture


def test_real_invoke_tool_never_reissues_uncertain_autonomous_write(tmp_path):
    org_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    run_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    action = "hubspot.contacts.update"
    receiver = IndependentFixture(tmp_path / "provider.sqlite3", b"<h1>isolated</h1>", capability="autonomous-cap")
    calls = []
    def executor(ctx, params):
        calls.append(ctx.autonomous_write_guarded)
        body = json.dumps({"cap": "autonomous-cap"}).encode()
        req = urllib.request.Request(receiver.origin + "/write", data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.status == 204
        return NormalizedResult(success=True, action=action, data={"id": "contact-1"})

    ctx = ToolContext(
        settings=SimpleNamespace(write_authority_mode="enforce",
                                 write_invoke_idempotency_enabled=True,
                                 private_connector_runtime_enabled=False),
        client=MagicMock(), org_id=org_id, actor_id="actor", run_id=run_id,
        step_id="write-1", autonomous_write_guarded=True,
    )
    claims = iter([
        WriteClaimResult(outcome="claimed", claim_token="first", status="in_progress"),
        WriteClaimResult(outcome="blocked", status="uncertain", reason="reconciliation_required"),
    ])
    row = {"approval_status": "approved", "required_approvals": 1,
           "definition_snapshot": {}, "parameters": {}}
    try:
        with (
            write_authority("run", run_id),
            patch("app.services.capability_availability.is_capability_action", return_value=False),
            patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None),
            patch("app.services.canvas_write_gate.require_approved_authority_run", return_value=row),
            patch("app.services.conversation_write_guard.assert_org_write_allowed"),
            patch("app.services.agent_interrupt_service.enforce_interrupt"),
            patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda ctx,act,params:params),
            patch.object(tool_service, "_resolve_tool_executor", return_value=executor),
            patch("app.services.hipaa_service.enforce_hipaa_for_tool_invoke"),
            patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits"),
            patch.object(tool_service, "assert_agent_tool_permission"),
            patch.object(tool_service, "_write_tool_audit"),
            patch("app.services.workflow_approval_scope.block_invoke_by_approval_scope", return_value=None),
            patch("app.services.compensation_service.should_track_compensation", return_value=False),
            patch("app.services.write_invoke_idempotency.claim_approved_autonomous_write", side_effect=lambda *a,**k:next(claims)),
            patch("app.services.write_invoke_idempotency.finalize_write_invoke"),
            patch("app.workers.workflow_queue.assert_current_workflow_claim_live"),
        ):
            result = tool_service.invoke_tool(ctx, action, {"id": "contact-1"})
            assert result.success is True
            assert receiver.writes == 1
            with pytest.raises(Exception, match="reconciliation|already in progress"):
                tool_service.invoke_tool(ctx, action, {"id": "contact-1"})
            assert receiver.writes == 1
            assert calls == [True]
    finally:
        receiver.close()
