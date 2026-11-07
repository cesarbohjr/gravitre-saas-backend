"""P27-02/03 joined offline journey through actual routing and step handler.

Real: AgentSelector.select, Play run router preflight/dispatch, approval route,
execute_workflow_steps registered invoke_tool handler, sealed read gate, SQL
workflow status trigger, outbox relay and idempotent durable consumer.

Adapted: local tenant connector query, initial execute_workflow run creation,
approval/step repositories, terminal finalizer and outbound vendor transport.
The narrow disposable PG fixture does NOT contain canonical approvals or
workflow_steps schemas; this test is NOT unmodified production DB E2E or
external provider readback certification.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException

from tests.db.pg_harness import requires_pg
from tests.db.test_domain_event_outbox_pg import ORG, _PsqlRpcClient, _new_run, pg

pytestmark = requires_pg

@pytest.mark.asyncio
async def test_agent_play_approval_real_step_to_durable_consumer(pg, monkeypatch):
    from app.services import agent_selector, domain_events, work_loop_links
    from app.routers import plays, workflows
    from app.workflows import execute, handlers
    from app.services.tool_types import ToolContext, NormalizedResult
    from app.services.sealed_read_execution import invoke_compiled_read
    from app.services.connector_resource_resolver import ResourceResolution

    workflow_id = "22222222-2222-4222-8222-222222222222"
    definition = {"steps": [{
        "id": "synthetic-read", "name": "Read synthetic CRM", "type": "invoke_tool",
        "config": {"action": "hubspot.contacts.search", "query": "fixture", "limit": 1},
    }]}
    settings = SimpleNamespace(
        disable_execute=False, disable_connectors=False,
        write_authority_mode="enforce",
        connector_secrets_encryption_key="k" * 32,
    )
    client = MagicMock()
    def connector_table(name):
        assert name == "connectors"
        class Query:
            def __init__(self): self.filters = []
            def select(self, *args): return self
            def eq(self, k, v): self.filters.append((k, v)); return self
            def execute(self):
                return SimpleNamespace(data=[{"provider": "hubspot", "org_id": ORG,
                    "status": "connected"}] if ("org_id", ORG) in self.filters else [])
        return Query()
    monkeypatch.setattr(agent_selector, "get_supabase_client", lambda _: SimpleNamespace(table=connector_table))
    monkeypatch.setattr("app.services.meta_learning_service.get_meta_learning_service",
                        lambda _: SimpleNamespace(is_enabled=lambda: False))
    selected = await agent_selector.AgentSelector(settings=settings).select(
        ORG, {"department": "sales", "intent": "sales_task",
              "requires_action": True, "agent_manifest_role": "qa"})
    assert selected["agent_manifest"]["role"] == "qa"
    assert selected["requires_swarm"]
    assert "hubspot" in await agent_selector.AgentSelector(settings=settings)._get_connected(ORG)

    run_id = None
    play_parameters = None
    monkeypatch.setattr(plays, "get_supabase_client", lambda _: client)
    monkeypatch.setattr(plays, "_load_installation", lambda *a, **kw:
                        {"id": "fixture-install", "operating_mode": "ACT WITH APPROVAL"})
    monkeypatch.setattr(work_loop_links, "resolve_run_links", lambda *a, **kw: (None, None))
    monkeypatch.setattr(plays, "connected_vendors", lambda *a, **kw: {"hubspot"})
    monkeypatch.setattr(plays, "resolve_play_readiness", lambda *a, **kw:
                        SimpleNamespace(act_with_approval_ready=True))
    monkeypatch.setattr(plays, "_observed_signals", lambda *a, **kw: set())
    monkeypatch.setattr(plays, "list_play_workflow_bindings", lambda *a, **kw:
                        [{"workflowId": workflow_id}])
    monkeypatch.setattr(plays, "get_workflow_def", lambda *a, **kw: {"id": workflow_id})
    monkeypatch.setattr(plays, "resolve_policy", lambda *a, **kw: (1, ["admin"]))
    monkeypatch.setattr(plays, "write_audit_event", lambda *a, **kw: None)

    async def initial_execute(body, *, current_user, org_id, environment_name, settings):
        nonlocal run_id, play_parameters
        assert org_id == ORG and environment_name == "synthetic"
        assert str(body.workflow_id) == workflow_id and body.play_key == "customer-rescue"
        play_parameters = body.parameters
        assert play_parameters["play"]["execution_authority"] == "canonical_workflow_runtime"
        assert pg.value("SELECT count(*) FROM public.workflow_runs") == "0"
        run_id = _new_run(pg, "pending_approval")
        return {"run_id": run_id, "status": "pending_approval", "approval_required": True}

    # The Play router is production code, but initial workflow creation is an
    # adapter because the isolated outbox schema lacks the canonical run contract.
    monkeypatch.setattr(workflows, "execute_workflow", initial_execute)
    response = await plays.run_play("customer-rescue",
        plays.RunPlayRequest(installationId="fixture-install"),
        ({"user_id": "synthetic-owner"}, ORG, "admin"), "synthetic", settings)
    assert response["workflowRuns"][0]["runId"] == run_id
    assert response["status"] == "awaiting_approval"
    assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "pending_approval"
    assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "0"

    approvals = []
    step_rows = [{
        "id": "synthetic-step-1", "step_id": "synthetic-read",
        "step_type": "invoke_tool", "status": "pending", "output_snapshot": {},
    }]
    statuses = ["pending"]
    def current_run(_client, org, rid, env):
        assert (org, rid, env) == (ORG, run_id, "synthetic")
        return {"id": run_id, "org_id": ORG,
                "status": pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'"),
                "run_type": workflows.RUN_TYPE_EXECUTE, "required_approvals": 1,
                "definition_snapshot": definition, "parameters": play_parameters,
                "environment": "synthetic", "steps": list(step_rows)}
    monkeypatch.setattr(workflows, "get_supabase_client", lambda _: client)
    monkeypatch.setattr(workflows, "get_plan_for_org", lambda *_: {"features": {"approvals": True}})
    monkeypatch.setattr(workflows, "require_feature", lambda *_: None)
    monkeypatch.setattr(workflows, "get_user_role", lambda *_: "admin")
    monkeypatch.setattr(workflows, "has_capability", lambda *_: True)
    monkeypatch.setattr(workflows, "get_run_with_steps", current_run)
    monkeypatch.setattr(workflows, "insert_run_approval",
                        lambda **kw: approvals.append(kw["approver_id"]))
    monkeypatch.setattr(workflows, "get_approval_counts", lambda *_: (len(approvals), False))
    monkeypatch.setattr("app.services.approval_record_service.finalize_contract_approval",
                        lambda *a, **kw: None)
    monkeypatch.setattr("app.services.transparency_service.record_human_override",
                        lambda *a, **kw: None)
    def claim(_client, rid, org):
        assert (rid, org) == (run_id, ORG)
        return pg.value(
            f"UPDATE public.workflow_runs SET status='running' "
            f"WHERE id='{run_id}' AND status='pending_approval' RETURNING id") == run_id
    monkeypatch.setattr(workflows, "try_mark_run_running", claim)
    for name in ("emit_execute_approval_recorded", "emit_execute_approved", "emit_execute_started"):
        monkeypatch.setattr(workflows, name, lambda *a, **kw: None)

    # Existing step rows were created at approval time; the real handler
    # must perform the pending -> running -> completed step transition.
    monkeypatch.setattr(execute, "enforce_interrupt", lambda *a, **kw: None)
    monkeypatch.setattr(execute, "get_run_with_steps", current_run)
    monkeypatch.setattr(execute, "set_step_running",
                        lambda _db, sid, _time: (
                            statuses.append("running"), step_rows[0].update(status="running")))
    def complete_step(**kw):
        statuses.append(kw["status"])
        step_rows[0].update(status=kw["status"], output_snapshot=kw.get("output_snapshot") or {})
    monkeypatch.setattr(execute, "update_step", complete_step)
    monkeypatch.setattr(execute, "emit_execute_step_completed", lambda *a, **kw: None)
    monkeypatch.setattr(execute, "write_audit_event", lambda *a, **kw: None)
    monkeypatch.setattr(execute, "resolve_active_branch", lambda *_: None)
    monkeypatch.setattr(execute, "should_skip_for_branch", lambda *a, **kw: False)
    monkeypatch.setattr(execute, "_add_run_execution_time", lambda *a, **kw: None)
    monkeypatch.setattr("app.services.action_selection_gate.gate_workflow_invoke",
                        lambda **kw: kw["action"])
    monkeypatch.setattr(handlers, "_enforce_canvas_write_authority",
                        lambda ctx: None if ctx.config["action"] == "hubspot.contacts.search"
                        else (_ for _ in ()).throw(AssertionError("unauthorized write")))
    vendor = Mock(return_value=NormalizedResult(
        success=True, action="hubspot.contacts.search",
        data={"results": [{"id": "synthetic-contact-1"}]}))
    resource = ResourceResolution(
        status="resolved", connector_id="hubspot", connection_id="local-conn",
        resource_type="portal", resource_id="99887", display_name="99887",
        confidence=0.98, resolution_reason="linked_config", candidate_count=1)
    def invoke(_context, action, params, **_kw):
        assert action == "hubspot.contacts.search"
        ctx = ToolContext(settings=settings, client=client, org_id=ORG,
                          actor_id="synthetic-approver", environment_name="synthetic")
        with (patch("app.services.read_preflight.resolve_resource", return_value=resource),
              patch("app.services.tool_service.enforce_rate_limit"),
              patch("app.services.tool_service.write_audit_event"),
              patch("app.services.agent_tool_permissions.list_agent_tool_permissions",
                    return_value=[{"connector_type": "hubspot",
                                   "scopes": ["hubspot:read"], "expires_at": None}]),
              patch("app.services.tool_service._resolve_tool_executor",
                    return_value=lambda *_: vendor())):
            return invoke_compiled_read(ctx, action, params)
    monkeypatch.setattr(handlers, "_invoke_canvas_registered_tool", invoke)
    def terminal_finalizer(_client, **kw):
        assert kw["org_id"] == ORG and kw["run_id"] == run_id
        assert kw["status"] == "completed"
        pg.psql(f"UPDATE public.workflow_runs SET status='completed' WHERE id='{run_id}'")
    monkeypatch.setattr("app.services.execution_outcome.finalize_execution_outcome",
                        terminal_finalizer)

    # No synthetic stand-in for the executor: route calls real implementation.
    monkeypatch.setattr(workflows, "execute_workflow_steps", execute.execute_workflow_steps)
    monkeypatch.setattr(workflows, "_step_to_out", lambda x: x)
    assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "0"
    approved = await workflows.approve_run(
        UUID(run_id), workflows.ApproveRejectRequest(comment="approved in QA"),
        {"user_id": "synthetic-approver"}, ORG, "synthetic", settings)
    assert approved["status"] == "completed"
    assert approved["approval_status"] == "approved"
    assert approvals == ["synthetic-approver"]
    assert statuses == ["pending", "running", "completed"]
    assert vendor.call_count == 1
    assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "completed"
    assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"
    with pytest.raises(HTTPException) as replay:
        await workflows.approve_run(
            UUID(run_id), workflows.ApproveRejectRequest(),
            {"user_id": "synthetic-approver"}, ORG, "synthetic", settings)
    assert replay.value.status_code == 400
    assert vendor.call_count == 1

    pg.psql("CREATE TABLE public.qa_p27_joined_effects ("
            "event_id bigint PRIMARY KEY, org_id uuid NOT NULL, run_id uuid NOT NULL)")
    def consumer(_client, event):
        assert event["org_id"] == ORG and event["aggregate_id"] == run_id
        pg.psql("INSERT INTO public.qa_p27_joined_effects (event_id,org_id,run_id) "
                f"VALUES ({int(event['id'])},'{ORG}','{run_id}') "
                "ON CONFLICT (event_id) DO NOTHING")
    domain_events.reset_domain_event_handlers_for_tests()
    domain_events.register_domain_event_handler(
        domain_events.EVENT_EXECUTION_OUTCOME_FINALIZED, "qa_p27_joined_consumer", consumer)
    try:
        relay = domain_events.DomainEventRelay(
            _PsqlRpcClient(pg), worker_id="qa-p27-joined-worker")
        first, repeated = relay.run_once(), relay.run_once()
    finally:
        domain_events.reset_domain_event_handlers_for_tests()
    assert first.delivered == 1 and repeated.claimed == 0
    assert pg.value("SELECT count(*) FROM public.qa_p27_joined_effects") == "1"
