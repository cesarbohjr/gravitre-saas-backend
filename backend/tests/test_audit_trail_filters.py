"""Audit trail redesign: action groups, outcome, search, server totals and filtered export."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.billing.service import DEFAULT_PLANS
from app.routers.audit import audit_category, audit_error_message, audit_outcome
from tests.support.build_insights import authenticate, chain_mock, clear_overrides, client, table_client

ACTOR_A = "00000000-0000-0000-0000-0000000000a1"
ACTOR_B = "00000000-0000-0000-0000-0000000000b2"


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    clear_overrides()


def _rows() -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        {
            "id": "e-1",
            "org_id": "org-1",
            "action": "source.sync.scheduled",
            "resource_type": "source",
            "resource_id": "s-1",
            "actor_id": ACTOR_A,
            "created_at": (now - timedelta(hours=1)).isoformat(),
            "details": {"status": "failed", "error": "Linked connector ID is required."},
        },
        {
            "id": "e-2",
            "org_id": "org-1",
            "action": "workflow.execute.completed",
            "resource_type": "workflow_run",
            "resource_id": "r-1",
            "actor_id": ACTOR_B,
            "created_at": (now - timedelta(hours=2)).isoformat(),
            "details": {"duration_ms": 412},
        },
        {
            "id": "e-3",
            "org_id": "org-1",
            "action": "tool.invoke.failed",
            "resource_type": "workflow_run",
            "resource_id": "r-2",
            "actor_id": ACTOR_A,
            "created_at": (now - timedelta(hours=3)).isoformat(),
            "details": {"action": "hubspot.contacts.create", "error": {"message": "HubSpot returned 401."}},
        },
        {
            "id": "e-4",
            "org_id": "org-1",
            "action": "settings.workspace_updated",
            "resource_type": "organization",
            "resource_id": "org-1",
            "actor_id": ACTOR_A,
            "created_at": (now - timedelta(hours=4)).isoformat(),
            "details": {},
        },
    ]


def _client():
    return table_client(
        {
            "audit_logs": chain_mock(data=_rows()),
            "users": chain_mock(
                data=[{"auth_user_id": ACTOR_A, "full_name": "Dana Admin", "email": "dana@example.com"}]
            ),
        }
    )


@pytest.mark.parametrize(
    ("action", "entity", "expected"),
    [
        ("source.sync.scheduled", "source", "sync"),
        ("rag.ingest.completed", "rag_source", "sync"),
        ("connector.connected", "connector", "sync"),
        ("workflow.execute.failed", "workflow_run", "run"),
        ("workflow.run.completed", "workflow", "run"),
        ("play.run.started", "play", "run"),
        ("approval.approved", "approval", "approve"),
        ("mcp.approval.decided", "mcp", "approve"),
        ("agent.created", "agent", "agent"),
        ("operator.version.activated", "operator", "agent"),
        ("department_member.added", "department", "member"),
        ("settings.approval_rules_updated", "organization", "setting"),
        ("environment.created", "environment", "setting"),
        ("tool.invoke.completed", "workflow_run", "chat"),
        ("assistant.execute_workflow", "workflow", "chat"),
        ("platform.health.snapshot", "platform", None),
    ],
)
def test_audit_category_maps_real_action_names(action, entity, expected):
    assert audit_category(action, entity) == expected


def test_audit_outcome_and_error_message():
    assert audit_outcome({"action": "tool.invoke.failed", "details": {}}) == "error"
    assert audit_outcome({"action": "connector.auth.expired", "details": {}}) == "error"
    assert audit_outcome({"action": "workflow.run.completed", "details": {"status": "failed"}}) == "error"
    assert audit_outcome({"action": "workflow.run.completed", "details": {"status": "completed"}}) == "success"
    assert audit_outcome({"action": "approval.rejected", "details": {}}) == "success"
    assert audit_error_message({"details": {"error": {"message": "HubSpot returned 401."}}}) == "HubSpot returned 401."
    assert audit_error_message({"details": {}}) is None


@patch("app.routers.audit.create_client")
@patch("app.routers.audit.get_plan_for_org", return_value=DEFAULT_PLANS["node"])
def test_list_returns_server_totals_for_filters(mock_plan, mock_create):
    mock_create.return_value = _client()
    authenticate()
    body = client.get("/api/audit?limit=1&offset=0").json()
    assert body["total"] == 4
    assert len(body["logs"]) == 1
    assert body["hasMore"] is True
    assert body["actors"] == 2
    assert body["errors"] == 2
    assert body["truncated"] is False
    first = body["logs"][0]
    assert first["category"] == "sync"
    assert first["outcome"] == "error"
    assert first["error_message"] == "Linked connector ID is required."
    # Actor ids resolve to names from the users table.
    assert first["user_name"] == "Dana Admin"
    assert first["user_email"] == "dana@example.com"


@patch("app.routers.audit.create_client")
@patch("app.routers.audit.get_plan_for_org", return_value=DEFAULT_PLANS["node"])
def test_list_filters_by_category_outcome_and_search(mock_plan, mock_create):
    mock_create.return_value = _client()
    authenticate()
    chat = client.get("/api/audit?category=chat").json()
    assert [log["id"] for log in chat["logs"]] == ["e-3"]
    errors = client.get("/api/audit?outcome=err").json()
    assert {log["id"] for log in errors["logs"]} == {"e-1", "e-3"}
    assert errors["total"] == 2 and errors["errors"] == 2
    ok = client.get("/api/audit?outcome=ok").json()
    assert {log["id"] for log in ok["logs"]} == {"e-2", "e-4"}
    # Search is server side, ignores dots/underscores and covers resolved names and details.
    assert [log["id"] for log in client.get("/api/audit?q=workflow%20execute").json()["logs"]] == ["e-2"]
    assert [log["id"] for log in client.get("/api/audit?q=hubspot").json()["logs"]] == ["e-3"]
    assert client.get("/api/audit?q=dana").json()["total"] == 3
    assert client.get(f"/api/audit?user_id={ACTOR_B}").json()["total"] == 1


@patch("app.routers.audit.create_client")
@patch("app.routers.audit.get_plan_for_org", return_value=DEFAULT_PLANS["node"])
def test_list_rejects_unknown_category(mock_plan, mock_create):
    mock_create.return_value = _client()
    authenticate()
    assert client.get("/api/audit?category=bogus").status_code == 422


@patch("app.routers.audit.create_client")
@patch("app.routers.audit.get_plan_for_org", return_value=DEFAULT_PLANS["node"])
def test_export_applies_the_same_filters_to_the_whole_range(mock_plan, mock_create):
    mock_create.return_value = _client()
    authenticate()
    body = client.get("/api/audit/export?format=json&outcome=err&range=7d").json()
    assert body["total"] == 2
    assert {log["id"] for log in body["logs"]} == {"e-1", "e-3"}
    csv_text = client.get("/api/audit/export?format=csv&category=setting").text
    lines = [line for line in csv_text.splitlines() if line]
    assert lines[0].endswith("category,outcome,error_message")
    assert len(lines) == 2 and "settings.workspace_updated" in lines[1]


@patch("app.routers.audit.create_client")
@patch("app.routers.audit.get_plan_for_org", return_value=DEFAULT_PLANS["node"])
def test_summary_reports_categories(mock_plan, mock_create):
    mock_create.return_value = _client()
    authenticate()
    body = client.get("/api/audit/summary?range=7d").json()
    assert body["byCategory"] == {"sync": 1, "run": 1, "chat": 1, "setting": 1}
    names = {row["user_id"]: row["user_name"] for row in body["byUser"]}
    assert names[ACTOR_A] == "Dana Admin"
