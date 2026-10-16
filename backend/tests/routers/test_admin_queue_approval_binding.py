"""Admin approval of a queued chat write executes exactly what was approved, once.

Before: create_contract_approval dropped the arguments (approvals has no
parameters column), the approve route selected that missing column, there was
no binding check and no claim, so the queue either could not execute or could
execute twice.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.config import Settings, get_settings
from app.main import app
from app.routers import workflows as workflows_module
from app.services.approval_action_binding import digest_plan_args
from app.services.approval_record_service import create_contract_approval

ORG = "org-1"
ARGS = {"to": "stephanie@example.com", "subject": "Hi", "body": "Hello"}


class _Query:
    def __init__(self, table: "_Table", op: str, patch: dict | None = None):
        self.table, self.op, self.patch, self.filters = table, op, patch, []

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self.filters.append(lambda r, c=col, v=val: str(r.get(c)) == str(v))
        return self

    def is_(self, col, val):
        assert val == "null"
        self.filters.append(lambda r, c=col: r.get(c) is None)
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        rows = [r for r in self.table.rows if all(f(r) for f in self.filters)]
        if self.op == "update":
            for r in rows:
                r.update(self.patch)
        return SimpleNamespace(data=[copy.deepcopy(r) for r in rows])


class _Table:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_a, **_k):
        return _Query(self, "select")

    def update(self, patch):
        return _Query(self, "update", patch)


class _Client:
    def __init__(self, rows):
        self.approvals = _Table(rows)

    def table(self, name):
        assert name == "approvals"
        return self.approvals


def _plan(args=None):
    return SimpleNamespace(
        tool_name="gmail", invoke_action="gmail.messages.send", integration="gmail",
        args=dict(args or ARGS), title="Send email",
    )


def _row(binding=True, args=None):
    ctx = {"conversation_id": "conv-1", "parameters": {"args": dict(ARGS)}}
    if binding:
        ctx["binding"] = {
            "tool_name": "gmail", "invoke_action": "gmail.messages.send", "integration": "gmail",
            "args_digest": digest_plan_args(args or ARGS),
        }
    return {
        "id": str(uuid4()), "org_id": ORG, "type": "connector_chat", "status": "pending",
        "context": ctx, "requested_by": "member-1", "reviewed_at": None, "reviewed_by": None,
    }


@pytest.fixture
def api(monkeypatch):
    audits: list[dict] = []
    execute = AsyncMock(return_value=SimpleNamespace(success=True, title="Send email", body="sent"))
    state = {"plan": _plan()}
    service = SimpleNamespace(plan_action=lambda *a, **k: state["plan"], execute_plan=execute)

    import app.services.chat_connector_execution_service as ccs
    import app.workflows.policy as policy
    import app.services.conversation_state_service as css

    monkeypatch.setattr(ccs, "get_chat_connector_execution_service", lambda _s: service)
    monkeypatch.setattr(policy, "get_user_role", lambda *_a: "admin")
    monkeypatch.setattr(
        css, "get_conversation_state_service",
        lambda _s: SimpleNamespace(update_task_state=AsyncMock()),
    )
    monkeypatch.setattr(workflows_module, "get_plan_for_org", lambda *_a: {"features": {"approvals": True}})
    monkeypatch.setattr(workflows_module, "require_feature", lambda *_a: None)
    monkeypatch.setattr(workflows_module, "write_audit_event", lambda _c, **kw: audits.append(kw))
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "admin-1"}
    app.dependency_overrides[get_org_context] = lambda: ORG
    app.dependency_overrides[get_environment_context] = lambda: "production"
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="dev", supabase_url="https://t.supabase.co", supabase_anon_key="a",
        supabase_service_role_key="s", supabase_jwt_secret="j",
    )
    yield SimpleNamespace(monkeypatch=monkeypatch, execute=execute, audits=audits, state=state)
    app.dependency_overrides.clear()


def _use(api, rows):
    client = _Client(rows)
    api.monkeypatch.setattr(workflows_module, "get_supabase_client", lambda _s: client)
    return client


def test_queue_record_keeps_the_arguments():
    inserted = {}

    class C:
        def table(self, _n):
            return self

        def insert(self, row):
            inserted.update(row)
            return self

        def execute(self):
            return SimpleNamespace(data=[inserted])

    create_contract_approval(C(), org_id=ORG, title="t", context={"conversation_id": "c"}, parameters={"args": ARGS})
    assert inserted["context"]["parameters"] == {"args": ARGS}
    assert inserted["context"]["conversation_id"] == "c"


def test_admin_approval_executes_once_and_is_audited(api):
    row = _row()
    _use(api, [row])
    resp = TestClient(app).post(f"/api/approvals/{row['id']}/approve", json={})
    assert resp.status_code == 200, resp.text
    assert api.execute.await_count == 1
    assert row["status"] == "approved" and row["reviewed_by"] == "admin-1"
    decided = [a for a in api.audits if a["action"] == "connector.approval.decided"]
    assert decided and decided[0]["metadata"]["args_digest"] == digest_plan_args(ARGS)
    # A second approve of the same row does nothing.
    again = TestClient(app).post(f"/api/approvals/{row['id']}/approve", json={})
    assert again.status_code == 409
    assert api.execute.await_count == 1


def test_claimed_row_is_not_executed_again(api):
    row = _row()
    row["reviewed_at"] = "2026-10-13T00:00:00Z"  # another approver's claim in flight
    _use(api, [row])
    resp = TestClient(app).post(f"/api/approvals/{row['id']}/approve", json={})
    assert resp.status_code == 409
    api.execute.assert_not_awaited()


def test_changed_arguments_are_refused(api):
    row = _row()
    _use(api, [row])
    api.state["plan"] = _plan({**ARGS, "to": "attacker@example.com"})
    resp = TestClient(app).post(f"/api/approvals/{row['id']}/approve", json={})
    assert resp.status_code == 409
    api.execute.assert_not_awaited()
    assert row["status"] == "pending" and row["reviewed_at"] is None
    assert any(a["action"] == "connector.approval.action_mismatch" for a in api.audits)


def test_rows_without_a_binding_are_refused(api):
    row = _row(binding=False)
    _use(api, [row])
    resp = TestClient(app).post(f"/api/approvals/{row['id']}/approve", json={})
    assert resp.status_code == 409
    api.execute.assert_not_awaited()


def test_non_admin_cannot_approve(api):
    import app.workflows.policy as policy

    api.monkeypatch.setattr(policy, "get_user_role", lambda *_a: "member")
    row = _row()
    _use(api, [row])
    resp = TestClient(app).post(f"/api/approvals/{row['id']}/approve", json={})
    assert resp.status_code == 403
    api.execute.assert_not_awaited()


@pytest.mark.parametrize("endpoint,approve", [("approve", True), ("reject", False)])
def test_mcp_decision_uses_shared_queue_route(api, endpoint, approve):
    row = {**_row(), "type": "mcp_tool"}
    _use(api, [row])
    decision = AsyncMock(return_value={"success": True, "status": "approved" if approve else "rejected", "verified": False})
    api.monkeypatch.setattr("app.services.mcp_approval_service.decide_mcp_approval", decision)
    response = TestClient(app).post(f"/api/approvals/{row['id']}/{endpoint}", json={})
    assert response.status_code == 200, response.text
    assert response.json()["verified"] is False
    assert decision.call_args.kwargs["approve"] is approve
    assert decision.call_args.kwargs["org_id"] == ORG
    assert decision.call_args.kwargs["reviewer_id"] == "admin-1"
    api.execute.assert_not_awaited()
