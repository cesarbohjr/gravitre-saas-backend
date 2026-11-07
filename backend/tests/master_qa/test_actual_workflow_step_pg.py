"""P27 integration slice: actual linear workflow step handler and SQL run state.

Runs the production execute_workflow_steps dispatcher and registered
InvokeToolHandler against a sealed local connector read. The test's PostgreSQL
cluster is real but its narrow schema lacks workflow_steps and all run contract
tables: those repository writes and terminal outcome fanout are explicitly
adapted to the disposable fixture. This DOES NOT certify an unmodified
production repository or approval-resume router.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from tests.db.pg_harness import requires_pg
from tests.db.test_domain_event_outbox_pg import ORG, _new_run, pg, _PsqlRpcClient

pytestmark = requires_pg


def test_real_invoke_tool_handler_runs_and_commits_authoritative_sql_outcome(pg, monkeypatch):
    from app.workflows import execute, handlers
    from app.services import domain_events
    from app.services.tool_types import NormalizedResult, ToolContext
    from app.services.sealed_read_execution import invoke_compiled_read
    from app.services.connector_resource_resolver import ResourceResolution

    run_id = _new_run(pg, status="pending_approval")
    assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "pending_approval"
    assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "0"

    # Simulates an already-approved workflow (not the real approve_run route).
    pg.psql(f"UPDATE public.workflow_runs SET status='running' WHERE id='{run_id}'")
    assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "running"

    local_vendor = Mock(return_value=NormalizedResult(
        success=True, action="hubspot.contacts.search",
        data={"results": [{"id": "synthetic-contact-1"}]},
    ))
    resource = ResourceResolution(
        status="resolved", connector_id="hubspot", connection_id="local-conn",
        resource_type="portal", resource_id="99887", display_name="99887",
        confidence=0.98, resolution_reason="linked_config", candidate_count=1,
    )
    settings = SimpleNamespace(disable_connectors=False,
        connector_secrets_encryption_key="k" * 32, write_authority_mode="enforce")
    db = MagicMock()
    persisted_steps = []
    statuses = []

    def create_step(**kwargs):
        step = {"id": "synthetic-step-1", "step_id": kwargs["step_id"],
                "step_type": kwargs["step_type"], "status": "pending", "output_snapshot": {}}
        persisted_steps.append(step)
        statuses.append("pending")
        return step

    def set_step_running(_client, step_id, _started_at):
        assert step_id == "synthetic-step-1"
        persisted_steps[0]["status"] = "running"
        statuses.append("running")

    def update_step(**kwargs):
        persisted_steps[0]["status"] = kwargs["status"]
        persisted_steps[0]["output_snapshot"] = kwargs.get("output_snapshot") or {}
        statuses.append(kwargs["status"])

    def get_run_with_steps(_client, _org, queried_run_id, _env):
        assert queried_run_id == run_id
        return {"workflow_id": "22222222-2222-4222-8222-222222222222",
                "status": pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'"),
                "steps": list(persisted_steps)}

    def local_invoke(_ctx, action, params, **_kw):
        assert action == "hubspot.contacts.search"
        ctx = ToolContext(
            settings=settings, client=db, org_id=ORG, actor_id="synthetic-owner",
            environment_name="synthetic",
        )
        with (
            patch("app.services.read_preflight.resolve_resource", return_value=resource),
            patch("app.services.tool_service.enforce_rate_limit"),
            patch("app.services.tool_service.write_audit_event"),
            patch("app.services.agent_tool_permissions.list_agent_tool_permissions",
                  return_value=[{"connector_type": "hubspot", "scopes": ["hubspot:read"], "expires_at": None}]),
            patch("app.services.tool_service._resolve_tool_executor",
                  return_value=lambda *_: local_vendor()),
        ):
            return invoke_compiled_read(ctx, action, params)

    def terminal_finalizer(_client, **kw):
        assert kw["run_id"] == run_id and kw["org_id"] == ORG
        # Schema-adapter for the fixture; actual outcome policy/fanout remains
        # a separate test because this cluster lacks canonical run contracts.
        pg.psql(f"UPDATE public.workflow_runs SET status='{kw['status']}' WHERE id='{run_id}'")

    monkeypatch.setattr(execute, "enforce_interrupt", lambda *a, **kw: None)
    monkeypatch.setattr(execute, "create_step", create_step)
    monkeypatch.setattr(execute, "set_step_running", set_step_running)
    monkeypatch.setattr(execute, "update_step", update_step)
    monkeypatch.setattr(execute, "get_run_with_steps", get_run_with_steps)
    monkeypatch.setattr(execute, "emit_execute_step_completed", lambda *a, **kw: None)
    monkeypatch.setattr(execute, "emit_execute_step_failed", lambda *a, **kw: None)
    monkeypatch.setattr(execute, "write_audit_event", lambda *a, **kw: None)
    monkeypatch.setattr(execute, "resolve_active_branch", lambda _v: None)
    monkeypatch.setattr(execute, "should_skip_for_branch", lambda *a, **kw: False)
    monkeypatch.setattr(execute, "_add_run_execution_time", lambda *a, **kw: None)
    monkeypatch.setattr(handlers, "_enforce_canvas_write_authority",
                        lambda ctx: None if ctx.config["action"] == "hubspot.contacts.search"
                        else (_ for _ in ()).throw(AssertionError("write cannot bypass gate")))
    monkeypatch.setattr(handlers, "_invoke_canvas_registered_tool", local_invoke)
    monkeypatch.setattr("app.services.action_selection_gate.gate_workflow_invoke", lambda **kw: kw["action"])
    monkeypatch.setattr("app.services.execution_outcome.finalize_execution_outcome", terminal_finalizer)

    definition = {"steps": [{
        "id": "synthetic-read", "name": "Read synthetic HubSpot contact",
        "type": "invoke_tool",
        "config": {"action": "hubspot.contacts.search", "query": "synthetic account", "limit": 1},
    }]}
    final, steps, errors, limited = execute.execute_workflow_steps(
        settings, ORG, "synthetic-owner", run_id, definition,
        {"play": {"key": "customer-rescue"}}, db, environment_name="synthetic",
    )
    assert final == "completed" and errors == [] and limited is False
    assert len(steps) == 1
    assert steps[0]["status"] == "completed"
    assert statuses == ["pending", "running", "completed"]
    assert local_vendor.call_count == 1
    assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "completed"
    assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"

    seen = []
    def consumer(_client, event):
        assert event["aggregate_id"] == run_id and event["org_id"] == ORG
        seen.append(event["id"])

    domain_events.reset_domain_event_handlers_for_tests()
    domain_events.register_domain_event_handler(
        domain_events.EVENT_EXECUTION_OUTCOME_FINALIZED, "qa_runtime_step_consumer", consumer)
    try:
        relay = domain_events.DomainEventRelay(_PsqlRpcClient(pg), worker_id="qa-runtime-worker")
        first, again = relay.run_once(), relay.run_once()
    finally:
        domain_events.reset_domain_event_handlers_for_tests()
    assert first.delivered == 1 and again.claimed == 0
    assert len(seen) == 1
