"""ECO-001 Agent worker -> governed tool -> independent provider -> PostgreSQL.

Real workflow_worker and registered invoke_tool handler dispatch are exercised.
Only the external Supabase RPC transport and ancillary step/notification readers
are adapted. The receiver is an independent test process, not live HubSpot.
"""
from __future__ import annotations

from contextlib import ExitStack
import json
import urllib.request
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services import tool_service
from app.services.tool_types import NormalizedResult
from app.services.write_invoke_idempotency import WriteClaimResult, WriteFinalizeResult
from app.workers.workflow_worker import process_workflow_run_job
from app.workers.workflow_queue import WorkflowRunJob
from app.workflows.registry import StepContext
from app.workflows import handlers
from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg
from tests.db.test_write_invoke_idempotency_pg import BOOTSTRAP_SQL, ORG_A, _claim, _finalize
from tests.db.test_autonomous_independent_write_pg import IndependentFixture

pytestmark = requires_pg


def test_authorized_agent_worker_matches_independent_receiver_and_durable_ledger(tmp_path):
    action = "hubspot.contacts.update"
    run_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    receiver = IndependentFixture(
        tmp_path / "agent-worker-provider.sqlite3", b"<h1>Worker QA</h1>",
        capability="agent-worker-cap",
    )
    migration = (MIGRATIONS / "20261016032018_write_invoke_idempotency.sql").read_text()
    grants = (MIGRATIONS / "20261016032029_write_invoke_idempotency_grants.sql").read_text()
    settings = SimpleNamespace(
        write_authority_mode="enforce",
        write_invoke_idempotency_enabled=True,
        private_connector_runtime_enabled=False,
    )
    client = MagicMock()
    run = {
        "id": run_id, "status": "running", "triggered_by": "actor",
        "definition_snapshot": {"steps": []},
        "parameters": {"_autonomous_run": True}, "environment": "acceptance",
    }
    authorization_row = {
        "approval_status": "approved", "required_approvals": 1,
        "definition_snapshot": {}, "parameters": {},
    }
    keys = []

    def provider(ctx, params):
        assert ctx.autonomous_write_guarded is True
        request = urllib.request.Request(
            receiver.origin + "/write",
            data=json.dumps({"cap": "agent-worker-cap"}).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=7) as response:
            assert response.status == 204
        return NormalizedResult(success=True, action=action, data={"id": "agent-qa"})

    def execute_registered_step(**kwargs):
        step = StepContext(
            settings=kwargs["settings"], org_id=kwargs["org_id"],
            user_id=kwargs["user_id"], run_id=kwargs["run_id"],
            environment_name=kwargs["environment_name"], step_id="write-1",
            step_type="invoke_tool", step_index=0, config={},
            parameters=kwargs["parameters"], step_outputs={},
            client=kwargs["client"], is_dry_run=False,
        )
        result = handlers._invoke_canvas_registered_tool(step, action, {"id": "agent-qa"})
        assert result.success
        return ("completed", [], [], False)

    job = WorkflowRunJob(run_id=run_id, org_id=ORG_A, workflow_id="qa-workflow")
    raw_job = json.dumps(job.__dict__)
    try:
        with pg_cluster(BOOTSTRAP_SQL, migration, grants) as pg:
            def claim(_client, *, org_id, idempotency_key, **_kw):
                assert org_id == ORG_A
                keys.append(idempotency_key)
                row = _claim(pg, org_id, idempotency_key)
                return WriteClaimResult(
                    outcome=row["outcome"], claim_token=row.get("claim_token"),
                    status=row.get("status"), reason=row.get("reason"),
                    replay=NormalizedResult(success=True, action=action, data={"id": "agent-qa"})
                    if row["outcome"] == "replay" else None,
                )

            def finalize(_client, *, org_id, idempotency_key, claim_token, status, **_kw):
                assert org_id == ORG_A and status == "completed"
                row = _finalize(pg, org_id, idempotency_key, claim_token, status)
                return WriteFinalizeResult(outcome=row["outcome"])

            with ExitStack() as stack:
                stack.enter_context(patch("app.workers.workflow_worker.get_supabase_client", return_value=client))
                stack.enter_context(patch("app.workers.workflow_worker.get_run_with_steps", return_value=run))
                stack.enter_context(patch("app.workers.workflow_worker.execute_workflow_steps", side_effect=execute_registered_step))
                stack.enter_context(patch("app.services.canvas_write_gate.bind_f1_write_hmac_context",
                                          side_effect=lambda **kw: (kw["tool_ctx"], kw["params"])))
                stack.enter_context(patch("app.services.sealed_read_execution.bind_read_preflight",
                                          side_effect=lambda ctx, act, params, **kw: (ctx, params, None)))
                stack.enter_context(patch("app.services.execution_outcome.finalize_execution_outcome"))
                stack.enter_context(patch("app.services.capability_availability.is_capability_action", return_value=False))
                stack.enter_context(patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None))
                stack.enter_context(patch("app.services.canvas_write_gate.require_approved_authority_run",
                                          return_value=authorization_row))
                stack.enter_context(patch("app.services.conversation_write_guard.assert_org_write_allowed"))
                stack.enter_context(patch("app.services.agent_interrupt_service.enforce_interrupt"))
                stack.enter_context(patch("app.services.write_preflight.enforce_invoke_write_preflight",
                                          side_effect=lambda ctx, act, params: params))
                stack.enter_context(patch.object(tool_service, "_resolve_tool_executor", return_value=provider))
                stack.enter_context(patch("app.services.hipaa_service.enforce_hipaa_for_tool_invoke"))
                stack.enter_context(patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits"))
                stack.enter_context(patch.object(tool_service, "assert_agent_tool_permission"))
                stack.enter_context(patch.object(tool_service, "_write_tool_audit"))
                stack.enter_context(patch("app.services.workflow_approval_scope.block_invoke_by_approval_scope",
                                          return_value=None))
                stack.enter_context(patch("app.services.compensation_service.should_track_compensation",
                                          return_value=False))
                stack.enter_context(patch("app.services.write_invoke_idempotency.claim_approved_autonomous_write",
                                          side_effect=claim))
                stack.enter_context(patch("app.services.write_invoke_idempotency.finalize_write_invoke",
                                          side_effect=finalize))
                stack.enter_context(patch("app.workers.workflow_queue.assert_current_workflow_claim_live"))
                assert process_workflow_run_job(settings, raw_job) is True
                assert receiver.writes == 1
                # Replay takes the same production worker -> handler -> invoke path,
                # but the durable claim prevents a second HTTP provider write.
                process_workflow_run_job(settings, raw_job)
                assert receiver.writes == 1
            assert len(keys) == 2 and keys[0] == keys[1]
            assert pg.value(
                "SELECT status FROM public.write_invoke_idempotency "
                f"WHERE org_id='{ORG_A}' AND idempotency_key='{keys[0]}'"
            ) == "completed"
            assert pg.value(
                "SELECT count(*) FROM public.write_invoke_idempotency "
                f"WHERE org_id='{ORG_A}' AND idempotency_key='{keys[0]}'"
            ) == "1"
    finally:
        receiver.close()
