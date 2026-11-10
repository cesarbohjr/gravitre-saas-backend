from contextlib import ExitStack
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
from app.services.write_invoke_idempotency import WriteClaimResult, WriteFinalizeResult
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

    from app.workers.workflow_worker import process_workflow_run_job
    from app.workers.workflow_queue import WorkflowRunJob
    from app.workflows.registry import StepContext
    from app.workflows import handlers

    settings = SimpleNamespace(write_authority_mode="enforce",
                               write_invoke_idempotency_enabled=True,
                               private_connector_runtime_enabled=False)
    client = MagicMock()
    run = {
        "id": run_id, "status": "running", "triggered_by": "actor",
        "definition_snapshot": {"steps": []},
        "parameters": {"_autonomous_run": True}, "environment": "acceptance",
    }
    def run_workflow(**kwargs):
        step = StepContext(
            settings=kwargs["settings"], org_id=kwargs["org_id"],
            user_id=kwargs["user_id"], run_id=kwargs["run_id"],
            environment_name=kwargs["environment_name"],
            step_id="write-1", step_type="invoke_tool", step_index=0,
            config={}, parameters=kwargs["parameters"], step_outputs={},
            client=kwargs["client"], is_dry_run=False,
        )
        result = handlers._invoke_canvas_registered_tool(step, action, {"id": "contact-1"})
        assert result.success
        return ("completed", [], [], False)
    job = WorkflowRunJob(run_id=run_id, org_id=org_id, workflow_id="wf-1")
    raw_job = json.dumps(job.__dict__)
    claims = iter([
        WriteClaimResult(outcome="claimed", claim_token="first", status="in_progress"),
        WriteClaimResult(outcome="blocked", status="uncertain", reason="reconciliation_required"),
    ])
    row = {"approval_status": "approved", "required_approvals": 1,
           "definition_snapshot": {}, "parameters": {}}
    try:
        with ExitStack() as stack:
            stack.enter_context(patch("app.workers.workflow_worker.get_supabase_client", return_value=client))
            stack.enter_context(patch("app.workers.workflow_worker.get_run_with_steps", return_value=run))
            stack.enter_context(patch("app.workers.workflow_worker.execute_workflow_steps", side_effect=run_workflow))
            stack.enter_context(patch("app.services.canvas_write_gate.bind_f1_write_hmac_context", side_effect=lambda **k: (k["tool_ctx"], k["params"])))
            stack.enter_context(patch("app.services.sealed_read_execution.bind_read_preflight", side_effect=lambda ctx, act, params, **kw: (ctx, params, None)))
            stack.enter_context(patch("app.services.execution_outcome.finalize_execution_outcome"))
            stack.enter_context(patch("app.services.capability_availability.is_capability_action", return_value=False))
            stack.enter_context(patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None))
            stack.enter_context(patch("app.services.canvas_write_gate.require_approved_authority_run", return_value=row))
            stack.enter_context(patch("app.services.conversation_write_guard.assert_org_write_allowed"))
            stack.enter_context(patch("app.services.agent_interrupt_service.enforce_interrupt"))
            stack.enter_context(patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda ctx,act,params:params))
            stack.enter_context(patch.object(tool_service, "_resolve_tool_executor", return_value=executor))
            stack.enter_context(patch("app.services.hipaa_service.enforce_hipaa_for_tool_invoke"))
            stack.enter_context(patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits"))
            stack.enter_context(patch.object(tool_service, "assert_agent_tool_permission"))
            stack.enter_context(patch.object(tool_service, "_write_tool_audit"))
            stack.enter_context(patch("app.services.workflow_approval_scope.block_invoke_by_approval_scope", return_value=None))
            stack.enter_context(patch("app.services.compensation_service.should_track_compensation", return_value=False))
            stack.enter_context(patch("app.services.write_invoke_idempotency.claim_approved_autonomous_write", side_effect=lambda *a,**k:next(claims)))
            stack.enter_context(patch("app.services.write_invoke_idempotency.finalize_write_invoke", return_value=WriteFinalizeResult(outcome="finalized")))
            stack.enter_context(patch("app.workers.workflow_queue.assert_current_workflow_claim_live"))
            assert process_workflow_run_job(settings, raw_job) is True
            assert receiver.writes == 1
            # Retry enters the same real worker/handler/invoke path and is
            # refused by the durable claim response before any provider call.
            assert process_workflow_run_job(settings, raw_job) is False
            assert receiver.writes == 1
            assert calls == [True]
    finally:
        receiver.close()
