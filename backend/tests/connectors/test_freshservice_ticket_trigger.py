"""Freshservice ticket event → governed workflow run (Release 3 measurable path).

Covers the inbound half of: signed event → run → approval → update_status →
read-back. The approval floor and read-back are the shared workflow paths
(tested in test_event_triggered_runs and the field-assert verifier); here we
prove a Freshservice event reaches them with the right identity and dedupe key.
"""
from __future__ import annotations

import base64
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.connectors import freshservice_webhooks as fw
from app.services import freshservice_trigger_service as fts

KEY = "d" * 64
SECRET = "fs-secret-123"

UPDATE_STATUS_WORKFLOW = {
    "schema_version": "v1",
    "steps": [
        {
            "id": "resolve",
            "name": "Resolve ticket",
            "type": "invoke_tool",
            "config": {
                "action": "freshservice.tickets.update_status",
                "params": {"ticket_id": "{{ticket_id}}", "status": 4},
            },
        }
    ],
}


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    import app.config as cfg

    monkeypatch.setattr(cfg, "get_settings", lambda: SimpleNamespace(connector_secrets_encryption_key=KEY))


# --- verification -----------------------------------------------------------


def _basic(password: str, user: str = "freshservice") -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def test_secret_header_or_basic_password_verifies():
    assert fw.verify_freshservice_webhook(secret=SECRET, header_secret=SECRET, authorization=None)
    assert fw.verify_freshservice_webhook(secret=SECRET, header_secret=None, authorization=_basic(SECRET))


@pytest.mark.parametrize(
    "header,auth",
    [(None, None), ("wrong", None), (None, _basic("wrong")), (None, "Basic !!notb64"), (None, "Bearer " + SECRET)],
)
def test_wrong_or_missing_secret_is_refused(header, auth):
    assert not fw.verify_freshservice_webhook(secret=SECRET, header_secret=header, authorization=auth)


def test_empty_configured_secret_never_verifies():
    assert not fw.verify_freshservice_webhook(secret="", header_secret="", authorization=_basic(""))


# --- normalisation and dedupe ----------------------------------------------


def test_normalizes_automator_placeholders():
    n = fw.normalize_freshservice_event(
        {"event": "ticket_updated", "ticket_id": "#INC-42", "status": "Open", "updated_at": "2026-10-13T10:00:00Z"}
    )
    assert n["event"] == "ticket.updated"
    assert n["ticket_id"] == "42"
    assert n["ticket"]["status"] == "open"


def test_numeric_status_maps_to_name_and_missing_id_is_unusable():
    assert fw.normalize_freshservice_event({"ticket": {"id": 7, "status": 4}})["ticket"]["status"] == "resolved"
    assert fw.normalize_freshservice_event({"event": "ticket.updated", "subject": "no id"}) is None
    assert fw.normalize_freshservice_event({"ticket_id": "../../x"}) is None


def test_event_id_is_stable_for_retries_and_changes_with_the_change():
    base = {"event": "ticket.updated", "ticket_id": "42", "status": "Open", "updated_at": "t1"}
    a = fw.freshservice_event_id(base, fw.normalize_freshservice_event(base))
    again = fw.freshservice_event_id(dict(base), fw.normalize_freshservice_event(dict(base)))
    moved = {**base, "status": "Pending", "updated_at": "t2"}
    b = fw.freshservice_event_id(moved, fw.normalize_freshservice_event(moved))
    assert a == again and a != b
    explicit = {**base, "event_id": "abc"}
    assert fw.freshservice_event_id(explicit, fw.normalize_freshservice_event(explicit)) == "fs:abc"


def test_trigger_matching_with_status_filter():
    t = {"event": "ticket.updated", "status": "pending", "workflow_id": "wf", "active": True}
    assert fw.event_matches_trigger(t, event="ticket.updated", status="pending")
    assert fw.event_matches_trigger(t, event="ticket.status_changed", status="pending")
    assert not fw.event_matches_trigger(t, event="ticket.updated", status="open")
    assert not fw.event_matches_trigger({**t, "active": False}, event="ticket.updated", status="pending")
    assert not fw.event_matches_trigger(
        {"event": "ticket.created", "workflow_id": "wf"}, event="ticket.updated", status=None
    )


# --- event → governed run ---------------------------------------------------


class _Client:
    """Just enough of the Supabase client for workflow + membership lookups."""

    def __init__(self, workflow: dict[str, Any], members: list[dict[str, Any]]) -> None:
        self.workflow, self.members, self._table = workflow, members, ""

    def table(self, name):
        self._table = name
        return self

    def select(self, *_a):
        return self

    def eq(self, *_a):
        return self

    def order(self, *_a):
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        if self._table == "workflow_defs":
            return SimpleNamespace(data=[dict(self.workflow)])
        if self._table == "organization_members":
            return SimpleNamespace(data=list(self.members))
        return SimpleNamespace(data=[])


CONNECTOR = {
    "id": "conn-fs",
    "org_id": "org-1",
    "type": "freshservice",
    "config": {
        "freshservice_triggers": [
            {"id": "t1", "event": "ticket.updated", "status": "pending", "workflow_id": "wf-fs",
             "active": True, "configured_by": "admin-1"}
        ]
    },
}
MEMBERS = [
    {"user_id": "member-1", "role": "member", "created_at": "1"},
    {"user_id": "admin-1", "role": "admin", "created_at": "2"},
]


@pytest.mark.asyncio
async def test_status_change_event_opens_pending_approval_for_ticket_write():
    import app.main  # noqa: F401  (loads app.routers.workflows in app order; direct import is circular)

    client = _Client(
        {"id": "wf-fs", "org_id": "org-1", "status": "active", "definition": UPDATE_STATUS_WORKFLOW,
         "created_by": "member-1"},
        MEMBERS,
    )
    execution = AsyncMock()
    settings = SimpleNamespace(policy_allowed_envs="", policy_max_steps=0, policy_max_runtime_seconds=0,
                               disable_connectors=False)
    with (
        patch.object(fts, "get_supabase_client", return_value=client),
        patch("app.workflows.policy.resolve_policy", return_value=(0, [])),
        patch("app.billing.service.get_plan_for_org", return_value={}),
        patch("app.services.event_triggered_runs.claim_webhook_event", return_value="claimed") as claim,
        patch(
            "app.routers.workflows._open_pending_approval_run",
            return_value={"run_id": "run-p", "status": "pending_approval"},
        ) as pending,
        patch("app.services.event_triggered_runs.create_execute_run") as create,
    ):
        out = await fts.process_freshservice_event_batch(
            settings,
            CONNECTOR,
            [{"event": "ticket.updated", "ticket_id": "42", "status": "Pending", "updated_at": "t9"}],
            execution_service=execution,
        )
    assert out[0]["status"] == "pending_approval"
    assert out[0]["connector_id"] == "conn-fs"
    kw = pending.call_args.kwargs
    # The ticket write cannot run without a human approval.
    assert kw["required_approvals"] >= 1 and kw["approval_floor_applied"] is True
    assert kw["trigger_type"] == "freshservice"
    # Attributed to the admin who configured the trigger, not an arbitrary member.
    assert kw["actor_id"] == "admin-1"
    assert claim.call_args.kwargs["event_id"].startswith("fs:")
    create.assert_not_called()
    execution.execute_workflow.assert_not_called()


@pytest.mark.asyncio
async def test_non_matching_status_starts_nothing():
    with patch.object(fts, "start_workflow_from_freshservice", new=AsyncMock()) as start:
        out = await fts.process_freshservice_event_batch(
            SimpleNamespace(), CONNECTOR, [{"event": "ticket.updated", "ticket_id": "42", "status": "Open"}]
        )
    assert out == []
    start.assert_not_called()


# --- inbound HTTP -----------------------------------------------------------


def _app(monkeypatch, connector: dict[str, Any] | None):
    from app.config import get_settings
    from app.routers.webhooks import freshservice_inbound as inbound

    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[connector] if connector else []
    )
    monkeypatch.setattr(inbound, "shared_service_client", lambda *_a: db)
    calls: list = []

    async def batch(_settings, conn, events, **_k):
        calls.append((conn["id"], events))
        return [{"status": "pending_approval"}]

    monkeypatch.setattr(inbound, "process_freshservice_event_batch", batch)
    app = FastAPI()
    app.include_router(inbound.router)
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(connector_secrets_encryption_key=KEY)
    return TestClient(app), calls


def _sealed_connector(**extra: Any) -> dict[str, Any]:
    from app.connectors.crypto import encrypt_secret

    return {**CONNECTOR, "config": {**CONNECTOR["config"], "webhook_secret_encrypted": encrypt_secret(SECRET, KEY)},
            **extra}


URL = "/api/webhooks/freshservice/inbound/conn-fs"
BODY = json.dumps({"event": "ticket.updated", "ticket_id": "42", "status": "Pending"})


def test_inbound_accepts_header_secret(monkeypatch):
    client, calls = _app(monkeypatch, _sealed_connector())
    r = client.post(URL, content=BODY, headers={fw.SECRET_HEADER: SECRET})
    assert r.status_code == 200, r.text
    assert calls[0][0] == "conn-fs"


def test_inbound_accepts_basic_auth(monkeypatch):
    client, calls = _app(monkeypatch, _sealed_connector())
    assert client.post(URL, content=BODY, headers={"Authorization": _basic(SECRET)}).status_code == 200


def test_inbound_refuses_wrong_secret(monkeypatch):
    client, calls = _app(monkeypatch, _sealed_connector())
    assert client.post(URL, content=BODY, headers={fw.SECRET_HEADER: "nope"}).status_code == 401
    assert calls == []


def test_inbound_without_configured_secret_fails_closed(monkeypatch):
    client, calls = _app(monkeypatch, {**CONNECTOR})
    assert client.post(URL, content=BODY, headers={fw.SECRET_HEADER: ""}).status_code == 401
    assert calls == []


@pytest.mark.parametrize("connector", [None, {**CONNECTOR, "type": "segment"}, {**CONNECTOR, "deleted_at": "x"}])
def test_inbound_unknown_wrong_type_or_deleted_connector_is_404(monkeypatch, connector):
    client, calls = _app(monkeypatch, connector)
    assert client.post(URL, content=BODY, headers={fw.SECRET_HEADER: SECRET}).status_code == 404


def test_inbound_rejects_oversized_body(monkeypatch):
    client, _ = _app(monkeypatch, _sealed_connector())
    big = "x" * (256 * 1024 + 1)
    assert client.post(URL, content=big, headers={fw.SECRET_HEADER: SECRET}).status_code == 413
