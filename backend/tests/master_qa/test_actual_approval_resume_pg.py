"""P27 approval-route regression against durable disposable SQL run transitions.

The production FastAPI approve_run function is real. Approval store,
notifications, and executor are injected local test adapters because the
narrow PostgreSQL outbox fixture lacks production approvals/run_steps tables.
This certifies router claim ordering, not a full live approval workflow.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException

from tests.db.pg_harness import requires_pg
from tests.db.test_domain_event_outbox_pg import ORG, _new_run, pg

pytestmark = requires_pg


@pytest.mark.asyncio
async def test_actual_approve_route_claims_pending_run_once_then_durable_terminal(pg, monkeypatch):
    from app.routers import workflows

    run_id = _new_run(pg, "pending_approval")
    approvals = []
    invoked = []
    client = MagicMock()
    monkeypatch.setattr(workflows, "get_supabase_client", lambda _settings: client)
    monkeypatch.setattr(workflows, "get_plan_for_org", lambda *_: {"features": {"approvals": True}})
    monkeypatch.setattr(workflows, "require_feature", lambda *_: None)
    monkeypatch.setattr(workflows, "get_user_role", lambda *_: "admin")
    monkeypatch.setattr(workflows, "has_capability", lambda *_: True)
    monkeypatch.setattr(workflows, "insert_run_approval",
                        lambda **kwargs: approvals.append(kwargs["approver_id"]))
    monkeypatch.setattr(workflows, "get_approval_counts",
                        lambda *_: (len(approvals), False))
    monkeypatch.setattr("app.services.approval_record_service.finalize_contract_approval",
                        lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.services.transparency_service.record_human_override",
                        lambda *_args, **_kwargs: None)

    def current_run(_client, org, rid, env):
        assert org == ORG and rid == run_id and env == "synthetic"
        state = pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'")
        return {
            "id": run_id, "org_id": ORG, "status": state,
            "run_type": workflows.RUN_TYPE_EXECUTE,
            "required_approvals": 1,
            "definition_snapshot": {"steps": [{"id": "s1", "type": "noop", "name": "Local noop"}]},
            "parameters": {}, "environment": "synthetic", "steps": [],
        }

    monkeypatch.setattr(workflows, "get_run_with_steps", current_run)
    def claim(_client, rid, org):
        assert rid == run_id and org == ORG
        changed = pg.value(
            f"UPDATE public.workflow_runs SET status='running' "
            f"WHERE id='{run_id}' AND status='pending_approval' RETURNING id"
        )
        return changed == run_id
    monkeypatch.setattr(workflows, "try_mark_run_running", claim)
    for name in ("emit_execute_approval_recorded", "emit_execute_approved", "emit_execute_started"):
        monkeypatch.setattr(workflows, name, lambda *_args, **_kwargs: None)

    def local_executor(_settings, org, user, rid, definition, parameters,
                       _client, env, steps_exist):
        assert org == ORG and rid == run_id and env == "synthetic"
        assert steps_exist is True and user == "synthetic-approver"
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "running"
        invoked.append(rid)
        pg.psql(f"UPDATE public.workflow_runs SET status='completed' WHERE id='{run_id}'")
        return "completed", [], [], False

    monkeypatch.setattr(workflows, "execute_workflow_steps", local_executor)
    monkeypatch.setattr(workflows, "_step_to_out", lambda x: x)
    settings = SimpleNamespace(disable_execute=False, disable_connectors=False)

    assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "0"
    response = await workflows.approve_run(
        UUID(run_id), workflows.ApproveRejectRequest(comment="synthetic QA approval"),
        {"user_id": "synthetic-approver"}, ORG, "synthetic", settings,
    )
    assert response["status"] == "completed"
    assert response["approval_status"] == "approved"
    assert invoked == [run_id]
    assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "completed"
    assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"

    with pytest.raises(HTTPException) as replay:
        await workflows.approve_run(
            UUID(run_id), workflows.ApproveRejectRequest(),
            {"user_id": "synthetic-approver"}, ORG, "synthetic", settings)
    assert replay.value.status_code == 400
    assert invoked == [run_id]
    assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"


@pytest.mark.asyncio
async def test_actual_approve_route_denies_missing_approver_capability_before_write(pg, monkeypatch):
    from app.routers import workflows

    run_id = _new_run(pg, "pending_approval")
    monkeypatch.setattr(workflows, "get_supabase_client", lambda *_: MagicMock())
    monkeypatch.setattr(workflows, "get_plan_for_org", lambda *_: {})
    monkeypatch.setattr(workflows, "require_feature", lambda *_: None)
    monkeypatch.setattr(workflows, "get_run_with_steps", lambda *_: {
        "run_type": workflows.RUN_TYPE_EXECUTE,
        "status": workflows.RUN_STATUS_PENDING_APPROVAL,
    })
    monkeypatch.setattr(workflows, "get_user_role", lambda *_: "member")
    monkeypatch.setattr(workflows, "has_capability", lambda *_: False)
    monkeypatch.setattr(workflows, "insert_run_approval",
                        lambda **kwargs: (_ for _ in ()).throw(AssertionError("approval written")))
    with pytest.raises(HTTPException) as rejected:
        await workflows.approve_run(UUID(run_id), workflows.ApproveRejectRequest(),
            {"user_id": "synthetic-unprivileged"}, ORG, "synthetic",
            SimpleNamespace(disable_execute=False))
    assert rejected.value.status_code == 403
    assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "pending_approval"
    assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "0"
