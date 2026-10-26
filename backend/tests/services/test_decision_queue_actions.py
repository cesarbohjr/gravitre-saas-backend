"""Decision queue: edit before approving, delegate and snooze a pending request."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.services import decision_queue_actions as dqa
from tests.support.fake_supabase import FakeQuery, FakeResponse, FakeSupabase

ORG = "org-1"
ENV = "production"
RUN_ID = "11111111-1111-1111-1111-111111111111"
MCP_ID = "22222222-2222-2222-2222-222222222222"
EXT_ID = "33333333-3333-3333-3333-333333333333"


class Query(FakeQuery):
    """Adds the in_/upsert surface the queue state table uses."""

    def in_(self, column, values):
        self.filters.append((column, ("__in__", tuple(values))))
        return self

    def upsert(self, payload, on_conflict=""):
        self.op = "upsert"
        self.payload = payload
        self.conflict = [c.strip() for c in on_conflict.split(",") if c.strip()]
        return self

    def _matches(self, row):
        for col, val in self.filters:
            if isinstance(val, tuple) and val and val[0] == "__in__":
                if row.get(col) not in val[1]:
                    return False
            elif row.get(col) != val:
                return False
        return True

    def execute(self):
        if self.op != "upsert":
            return super().execute()
        rows = self.client.tables.setdefault(self.table, [])
        for row in rows:
            if all(row.get(c) == self.payload.get(c) for c in self.conflict):
                row.update(copy.deepcopy(self.payload))
                return FakeResponse([copy.deepcopy(row)])
        rows.append(copy.deepcopy(self.payload))
        return FakeResponse([copy.deepcopy(self.payload)])


class Client(FakeSupabase):
    def table(self, name):
        return Query(self, name)


@pytest.fixture
def client(monkeypatch):
    c = Client()
    c.tables["organization_members"] = [
        {"org_id": ORG, "user_id": "admin-1", "role": "admin"},
        {"org_id": ORG, "user_id": "admin-2", "role": "admin"},
        {"org_id": ORG, "user_id": "viewer-1", "role": "viewer"},
    ]
    c.tables["workflow_runs"] = [
        {
            "id": RUN_ID,
            "org_id": ORG,
            "environment": ENV,
            "status": "pending_approval",
            "approval_status": "pending_approval",
            "parameters": {"list": "MSP Prospect", "count": 24, "source": "chat_orchestration"},
        }
    ]
    c.tables["approvals"] = [
        {
            "id": MCP_ID,
            "org_id": ORG,
            "type": "mcp_tool",
            "status": "pending",
            "reviewed_at": None,
            "context": {"mcp_execution_id": "exec-1", "parameters": {"q": "old"}, "input_sha256": "x"},
        },
        {"id": EXT_ID, "org_id": ORG, "type": "extension_write", "status": "pending", "reviewed_at": None, "context": {}},
    ]
    c.tables["mcp_tool_executions"] = [
        {"id": "exec-1", "org_id": ORG, "approval_id": MCP_ID, "status": "pending_approval", "input": {"q": "old"}}
    ]
    monkeypatch.setattr(dqa, "has_capability", lambda _c, _o, role, _cap: role in {"admin", "owner"})
    monkeypatch.setattr(dqa, "write_audit_event", lambda *a, **k: None)
    return c


def test_edit_run_keeps_platform_keys_and_records_the_original(client):
    out = dqa.edit_request(
        client, None, org_id=ORG, environment_name=ENV, approval_id=RUN_ID, user_id="admin-1",
        parameters={"list": "MSP Prospect", "count": 10, "source": "forged"},
    )
    assert out["parameters"]["count"] == 10
    run = client.rows("workflow_runs", id=RUN_ID)[0]
    assert run["parameters"] == {"list": "MSP Prospect", "count": 10, "source": "chat_orchestration"}
    state = client.rows("decision_queue_states", approval_id=RUN_ID)[0]
    assert state["edited_by"] == "admin-1"
    assert state["original_parameters"]["count"] == 24

    # A second edit keeps the first version the agent asked for.
    dqa.edit_request(
        client, None, org_id=ORG, environment_name=ENV, approval_id=RUN_ID, user_id="admin-1",
        parameters={"list": "MSP Prospect", "count": 5},
    )
    assert client.rows("decision_queue_states", approval_id=RUN_ID)[0]["original_parameters"]["count"] == 24


def test_edit_mcp_rebinds_input_hash(client):
    from app.services.mcp_client_service import mcp_input_sha256

    dqa.edit_request(
        client, None, org_id=ORG, environment_name=ENV, approval_id=MCP_ID, user_id="admin-1", parameters={"q": "new"}
    )
    execution = client.rows("mcp_tool_executions", id="exec-1")[0]
    ctx = client.rows("approvals", id=MCP_ID)[0]["context"]
    assert execution["input"] == {"q": "new"}
    assert ctx["parameters"] == {"q": "new"}
    assert ctx["input_sha256"] == mcp_input_sha256({"q": "new"})


def test_extension_writes_cannot_be_edited(client):
    with pytest.raises(HTTPException) as exc:
        dqa.edit_request(
            client, None, org_id=ORG, environment_name=ENV, approval_id=EXT_ID, user_id="admin-1", parameters={"a": 1}
        )
    assert exc.value.status_code == 409


def test_viewer_cannot_edit_snooze_or_delegate(client):
    with pytest.raises(HTTPException) as exc:
        dqa.snooze_request(
            client, org_id=ORG, environment_name=ENV, approval_id=RUN_ID, user_id="viewer-1",
            until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    assert exc.value.status_code == 403


def test_resolved_requests_cannot_be_changed(client):
    client.tables["workflow_runs"][0]["status"] = "completed"
    with pytest.raises(HTTPException) as exc:
        dqa.snooze_request(
            client, org_id=ORG, environment_name=ENV, approval_id=RUN_ID, user_id="admin-1",
            until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    assert exc.value.status_code == 409


def test_snooze_bounds_and_unsnooze(client):
    soon = datetime.now(timezone.utc) + timedelta(minutes=1)
    with pytest.raises(HTTPException):
        dqa.snooze_request(client, org_id=ORG, environment_name=ENV, approval_id=RUN_ID, user_id="admin-1", until=soon)
    far = datetime.now(timezone.utc) + timedelta(days=8)
    with pytest.raises(HTTPException):
        dqa.snooze_request(client, org_id=ORG, environment_name=ENV, approval_id=RUN_ID, user_id="admin-1", until=far)

    later = datetime.now(timezone.utc) + timedelta(hours=3)
    dqa.snooze_request(client, org_id=ORG, environment_name=ENV, approval_id=RUN_ID, user_id="admin-1", until=later)
    assert client.rows("decision_queue_states", approval_id=RUN_ID)[0]["snoozed_by"] == "admin-1"
    dqa.snooze_request(client, org_id=ORG, environment_name=ENV, approval_id=RUN_ID, user_id="admin-1", until=None)
    assert client.rows("decision_queue_states", approval_id=RUN_ID)[0]["snoozed_until"] is None


def test_delegate_requires_an_approver_and_notifies(client, monkeypatch):
    sent = []
    import app.services.notification_emitter as emitter

    monkeypatch.setattr(emitter, "create_user_notification", lambda _c, **kw: sent.append(kw))
    with pytest.raises(HTTPException):
        dqa.delegate_request(
            client, org_id=ORG, environment_name=ENV, approval_id=RUN_ID, user_id="admin-1",
            delegate_to="viewer-1", note=None,
        )
    with pytest.raises(HTTPException):
        dqa.delegate_request(
            client, org_id=ORG, environment_name=ENV, approval_id=RUN_ID, user_id="admin-1",
            delegate_to="admin-1", note=None,
        )
    dqa.delegate_request(
        client, org_id=ORG, environment_name=ENV, approval_id=RUN_ID, user_id="admin-1",
        delegate_to="admin-2", note="You own this list",
    )
    state = client.rows("decision_queue_states", approval_id=RUN_ID)[0]
    assert state["delegated_to"] == "admin-2" and state["delegate_note"] == "You own this list"
    assert sent and sent[0]["user_id"] == "admin-2" and sent[0]["url"] == f"/approvals?id={RUN_ID}"


def test_apply_states_stamps_list_items():
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    items = [
        {"id": "a", "status": "pending", "gate_type": "execute", "request": {"count": 3, "source": "x"}, "context": {}},
        {"id": "b", "status": "pending", "gate_type": "browser_extension_write", "type": "connector", "context": {}},
    ]
    states = {
        "a": {"snoozed_until": future, "snoozed_by": "u1", "delegated_to": "u2", "delegated_by": "u1", "edited_at": past},
        "b": {"snoozed_until": past},
    }
    dqa.apply_states(items, states, {"u1": "Dana", "u2": "Sam"})
    assert items[0]["editable_parameters"] == {"count": 3}
    assert items[0]["snoozed_until"] and items[0]["delegated_to_name"] == "Sam" and items[0]["edited_at"] == past
    assert items[1]["editable_parameters"] is None and items[1]["edit_blocked_reason"]
    assert "snoozed_until" not in items[1]  # an expired snooze is back in the queue
