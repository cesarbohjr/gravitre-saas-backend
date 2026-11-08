"""P27-02/03 joined offline journey through actual routing and step handler.

Real: AgentSelector.select, Play run router preflight/dispatch, approval route,
execute_workflow_steps registered invoke_tool handler, sealed read gate, SQL
workflow status trigger, outbox relay and idempotent durable consumer.

Adapted: local tenant connector query, deterministic version/policy/billing,
terminal notification finalizer and outbound vendor transport.
Canonical repository methods and legacy/contract run, step and approval
tables are real, backed by disposable PostgreSQL via a SQL transport adapter.
This is NOT an unmodified production API/worker, process crash or external
provider readback certification.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException

from tests.db.pg_harness import requires_pg
from tests.db.test_domain_event_outbox_pg import ORG, _PsqlRpcClient
from tests.master_qa.canonical_pg_repository import (
    PgRepositoryClient, canonical_pg_cluster,
)

@pytest.fixture
def pg():
    with canonical_pg_cluster() as database:
        yield database

pytestmark = requires_pg

@pytest.mark.asyncio
async def test_agent_play_approval_real_step_to_durable_consumer(pg, monkeypatch):
    from app.services import agent_selector, domain_events, work_loop_links
    from app.routers import plays, workflows
    from app.workflows import execute, handlers, repository
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
        policy_allowed_envs="synthetic",
        policy_max_steps=10, policy_max_runtime_seconds=60,
    )
    client = PgRepositoryClient(pg)
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

    # Exercise production execute_workflow from Play dispatch. Policy, active
    # version, billing and notification side dependencies are deterministic;
    # repository creation/step insertion remain the original implementations.
    pg.psql(f"INSERT INTO public.workflows (id, org_id, name) "
            f"VALUES ('{workflow_id}', '{ORG}', 'Synthetic QA Play workflow')")
    monkeypatch.setattr(workflows, "get_supabase_client", lambda _: client)
    monkeypatch.setattr(workflows, "get_plan_for_org", lambda *a: {"features": {"approvals": True}})
    monkeypatch.setattr(workflows, "get_workflow_def", lambda *a: {"id": workflow_id})
    monkeypatch.setattr(workflows, "play_binding_for_workflow",
                        lambda *a, **kw: {"key": "customer-rescue", "version": "1"})
    monkeypatch.setattr(workflows, "get_active_workflow_version",
                        lambda *a: {"id": "33333333-3333-4333-8333-333333333333",
                                    "definition": definition})
    monkeypatch.setattr("app.workflows.definition_resolver.resolve_executable_definition",
                        lambda _client, _org, _workflow, definition, _env: definition)
    monkeypatch.setattr(workflows, "validate_definition", lambda value: value)
    monkeypatch.setattr(workflows, "validate_execute_steps", lambda value: None)
    monkeypatch.setattr(workflows, "enrich_vertical_workflow_parameters",
                        lambda _org, _workflow, parameters, _wf, **kw: parameters)
    monkeypatch.setattr(workflows, "resolve_policy", lambda *a: (1, ["admin"]))
    monkeypatch.setattr(workflows, "get_user_role", lambda *a: "admin")
    monkeypatch.setattr(workflows, "check_concurrency", lambda *a, **kw: None)
    monkeypatch.setattr(workflows, "evaluate_policy", lambda ctx:
                        SimpleNamespace(allowed=True, required_approvals=1,
                                        approver_roles=["admin"], approval_floor_applied=False))
    monkeypatch.setattr("app.services.org_approval_rules.required_approvals_for_definition",
                        lambda *a: 1)
    monkeypatch.setattr(workflows, "require_feature", lambda *a: None)
    monkeypatch.setattr(workflows, "_record_workflow_run_usage", lambda *a: None)
    monkeypatch.setattr(workflows, "write_audit_event", lambda *a, **kw: None)
    monkeypatch.setattr("app.services.workflow_approval_scope.persist_run_approval_scope",
                        lambda *a, **kw: None)
    monkeypatch.setattr("app.services.approval_record_service.sync_workflow_pending_approval",
                        lambda *a, **kw: None)
    for event_name in ("emit_execute_created", "emit_execute_pending_approval"):
        monkeypatch.setattr(workflows, event_name, lambda *a, **kw: None)
    # Use actual repository functions without replacing their write logic.
    monkeypatch.setattr(workflows, "create_execute_run", repository.create_execute_run)
    monkeypatch.setattr(workflows, "create_step", repository.create_step)
    production_execute = workflows.execute_workflow

    async def initial_execute(body, *, current_user, org_id, environment_name, settings):
        nonlocal run_id, play_parameters
        assert pg.value("SELECT count(*) FROM public.workflow_runs") == "0"
        assert org_id == ORG and str(body.workflow_id) == workflow_id
        assert body.play_key == "customer-rescue"
        result = await production_execute(
            body, current_user=current_user, org_id=org_id,
            environment_name=environment_name, settings=settings)
        run_id = result["run_id"]
        play_parameters = repository.get_run_with_steps(client, ORG, run_id,
                                                         "synthetic")["parameters"]
        assert play_parameters["play"]["execution_authority"] == "canonical_workflow_runtime"
        return result

    # Thin inspection wrapper, not an execution stub.
    monkeypatch.setattr(workflows, "execute_workflow", initial_execute)
    response = await plays.run_play("customer-rescue",
        plays.RunPlayRequest(installationId="fixture-install"),
        ({"user_id": "synthetic-owner"}, ORG, "admin"), "synthetic", settings)
    assert response["workflowRuns"][0]["runId"] == run_id
    assert response["status"] == "awaiting_approval"
    assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "pending_approval"
    assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "0"

    assert pg.value(f"SELECT count(*) FROM public.workflow_steps WHERE run_id='{run_id}'") == "1"
    monkeypatch.setattr(workflows, "get_supabase_client", lambda _: client)
    monkeypatch.setattr(workflows, "get_plan_for_org", lambda *_: {"features": {"approvals": True}})
    monkeypatch.setattr(workflows, "require_feature", lambda *_: None)
    monkeypatch.setattr(workflows, "get_user_role", lambda *_: "admin")
    monkeypatch.setattr(workflows, "has_capability", lambda *_: True)
    # Approval store, counts and run reader now use unpatched repository.
    monkeypatch.setattr(workflows, "get_run_with_steps", repository.get_run_with_steps)
    monkeypatch.setattr(workflows, "insert_run_approval", repository.insert_run_approval)
    monkeypatch.setattr(workflows, "get_approval_counts", repository.get_approval_counts)
    monkeypatch.setattr("app.services.approval_record_service.finalize_contract_approval",
                        lambda *a, **kw: None)
    monkeypatch.setattr("app.services.transparency_service.record_human_override",
                        lambda *a, **kw: None)
    monkeypatch.setattr(workflows, "try_mark_run_running", repository.try_mark_run_running)
    for name in ("emit_execute_approval_recorded", "emit_execute_approved", "emit_execute_started"):
        monkeypatch.setattr(workflows, name, lambda *a, **kw: None)

    # Existing step rows were created at approval time; the real handler
    # must perform the pending -> running -> completed step transition.
    monkeypatch.setattr(execute, "enforce_interrupt", lambda *a, **kw: None)
    # Production repository step reader and writers remain unpatched.
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
        # The connector vendor transport uses a local fake rather than the
        # restricted SQL repository client (whose scope is workflow state).
        ctx = ToolContext(settings=settings, client=MagicMock(), org_id=ORG,
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
        assert kw["status"] == "completed", (
            kw, repository.get_run_with_steps(_client, ORG, run_id, "synthetic")["steps"])
        # Pending canonical outcome notification fanout is adapted, but the
        # repository update and runs/run_steps mirrors are production code.
        repository.update_run(_client, run_id, "completed", approval_status="approved")
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
    assert repository.get_approval_counts(PgRepositoryClient(pg), run_id) == (1, False)
    steps = repository.get_run_with_steps(PgRepositoryClient(pg), ORG, run_id, "synthetic")["steps"]
    assert steps[0]["status"] == "completed"
    assert steps[0]["output_snapshot"]
    assert pg.value(f"SELECT status FROM public.runs WHERE id='{run_id}'") == "completed"
    assert pg.value(f"SELECT status FROM public.run_steps WHERE run_id='{run_id}'") == "completed"
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
        assert first.delivered == 1 and repeated.claimed == 0
        # Simulate an already-delivered event being replayed after transport
        # reconciliation. The business consumer must still persist ONE effect
        # by the immutable event ID, even if handler bookkeeping were lost.
        pg.psql(
            "UPDATE public.domain_event_outbox SET "
            "status='pending', available_at=now(), delivered_at=NULL, "
            "delivered_handlers='{}'::text[] "
            f"WHERE aggregate_id='{run_id}'")
        replayed = relay.run_once()
    finally:
        domain_events.reset_domain_event_handlers_for_tests()
    assert replayed.delivered == 1
    assert vendor.call_count == 1  # never replay the external provider operation
    assert pg.value("SELECT count(*) FROM public.qa_p27_joined_effects") == "1"
    assert pg.value(
        f"SELECT count(*) FROM public.domain_event_outbox "
        f"WHERE aggregate_id='{run_id}' AND status='delivered'") == "1"
