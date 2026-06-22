"""Audit trail API regression tests (BUILD/INSIGHTS audit spec)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from urllib.parse import quote

import pytest

from app.billing.service import DEFAULT_PLANS
from tests.support.build_insights import authenticate, chain_mock, clear_overrides, client, table_client


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    clear_overrides()


def _audit_rows() -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        {
            "id": "log-1",
            "org_id": "org-1",
            "action": "workflow.run.completed",
            "resource_type": "workflow",
            "resource_id": "wf-1",
            "entity_name": "sync-customers",
            "actor_id": "user-1",
            "actor": "Cesar",
            "created_at": (now - timedelta(hours=2)).isoformat(),
            "details": {"recordsProcessed": 10},
        },
        {
            "id": "log-2",
            "org_id": "org-1",
            "action": "connector.connected",
            "resource_type": "connector",
            "resource_id": "c-1",
            "actor_id": "user-2",
            "actor": "Alex",
            "created_at": (now - timedelta(days=2)).isoformat(),
            "details": {},
        },
        {
            "id": "log-3",
            "org_id": "org-1",
            "action": "workflow.run.failed",
            "resource_type": "workflow",
            "resource_id": "wf-2",
            "created_at": (now - timedelta(days=10)).isoformat(),
            "details": {},
        },
    ]


@patch("app.routers.audit.create_client")
@patch("app.routers.audit.get_plan_for_org", return_value=DEFAULT_PLANS["node"])
def test_audit_list_returns_logs(mock_plan, mock_create):
    mock_create.return_value = table_client(
        {"audit_logs": chain_mock(data=_audit_rows())}
    )
    authenticate()
    response = client.get("/api/audit")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["logs"]) == 3
    assert body["logs"][0]["action"] == "workflow.run.completed"


@patch("app.routers.audit.create_client")
@patch("app.routers.audit.get_plan_for_org", return_value=DEFAULT_PLANS["node"])
@patch("app.routers.audit._fetch_rows")
def test_audit_filters_by_action_type(mock_fetch, mock_plan, mock_create):
    mock_fetch.return_value = [row for row in _audit_rows() if row["action"] == "connector.connected"]
    mock_create.return_value = table_client({"audit_logs": chain_mock()})
    authenticate()
    response = client.get("/api/audit?action=connector.connected")
    assert response.status_code == 200
    logs = response.json()["logs"]
    assert len(logs) == 1
    assert logs[0]["action"] == "connector.connected"


@patch("app.routers.audit.create_client")
@patch("app.routers.audit.get_plan_for_org", return_value=DEFAULT_PLANS["node"])
def test_audit_filters_by_entity_type(mock_plan, mock_create):
    mock_create.return_value = table_client({"audit_logs": chain_mock(data=_audit_rows())})
    authenticate()
    response = client.get("/api/audit?entity_type=connector")
    assert response.status_code == 200
    logs = response.json()["logs"]
    assert len(logs) == 1
    assert logs[0]["entity_type"] == "connector"


@patch("app.routers.audit.create_client")
@patch("app.routers.audit.get_plan_for_org", return_value=DEFAULT_PLANS["node"])
def test_audit_filters_by_date_range(mock_plan, mock_create):
    mock_create.return_value = table_client({"audit_logs": chain_mock(data=_audit_rows())})
    authenticate()
    from_ts = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat().replace("+00:00", "Z")
    response = client.get(f"/api/audit?from={quote(from_ts, safe='')}")
    assert response.status_code == 200
    assert response.json()["total"] == 2


@patch("app.routers.audit.create_client")
@patch("app.routers.audit.get_plan_for_org", return_value=DEFAULT_PLANS["node"])
def test_audit_export_csv(mock_plan, mock_create):
    mock_create.return_value = table_client({"audit_logs": chain_mock(data=_audit_rows())})
    authenticate()
    response = client.get("/api/audit/export?format=csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "workflow.run.completed" in response.text


@patch("app.routers.audit.create_client")
@patch("app.routers.audit.get_plan_for_org", return_value=DEFAULT_PLANS["node"])
def test_audit_export_json(mock_plan, mock_create):
    mock_create.return_value = table_client({"audit_logs": chain_mock(data=_audit_rows())})
    authenticate()
    response = client.get("/api/audit/export?format=json")
    assert response.status_code == 200
    body = response.json()
    assert len(body["logs"]) == 3


@patch("app.routers.audit.create_client")
@patch("app.routers.audit.get_plan_for_org")
def test_audit_denied_without_entitlement(mock_plan, mock_create):
    plan = dict(DEFAULT_PLANS["node"])
    plan["features"] = dict(plan["features"])
    plan["features"]["audit_logs"] = False
    mock_plan.return_value = plan
    mock_create.return_value = table_client({"audit_logs": chain_mock(data=[])})
    authenticate()
    response = client.get("/api/audit")
    assert response.status_code == 403


@patch("app.workflows.audit._schedule_siem_dispatch")
@patch("app.workflows.audit._get_org_pii_mode", return_value="standard")
def test_audit_dual_write_gap_logged_when_logs_fail(mock_pii, mock_siem, caplog):
    from unittest.mock import MagicMock

    from app.workflows.audit import write_audit_event

    sb = MagicMock()
    table = sb.table.return_value
    insert = table.insert.return_value

    def execute_side_effect():
        call_table = sb.table.call_args[0][0]
        if call_table == "audit_logs":
            raise RuntimeError("audit_logs insert failed")
        return MagicMock(data=[{}])

    insert.execute.side_effect = execute_side_effect

    with caplog.at_level("WARNING"):
        write_audit_event(
            sb,
            org_id="org-1",
            actor_id="00000000-0000-0000-0000-000000000001",
            action="workflow.run.completed",
            resource_type="workflow",
            resource_id="00000000-0000-0000-0000-000000000002",
            metadata={},
        )

    assert any("audit_dual_write_gap" in record.message for record in caplog.records)


@patch("app.workflows.audit._schedule_siem_dispatch")
@patch("app.workflows.audit._get_org_pii_mode", return_value="standard")
def test_audit_events_written_on_workflow_run(mock_pii, mock_siem):
    from unittest.mock import MagicMock

    from app.workflows.audit import write_audit_event

    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])
    write_audit_event(
        sb,
        org_id="org-1",
        actor_id="user-1",
        action="workflow.run.completed",
        resource_type="workflow",
        resource_id="run-1",
        metadata={"recordsProcessed": 5},
    )
    insert_row = sb.table.return_value.insert.call_args[0][0]
    assert insert_row["action"] == "workflow.run.completed"


@patch("app.workflows.audit._schedule_siem_dispatch")
@patch("app.workflows.audit._get_org_pii_mode", return_value="standard")
def test_audit_events_written_on_connector_change(mock_pii, mock_siem):
    from unittest.mock import MagicMock

    from app.workflows.audit import write_audit_event

    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])
    write_audit_event(
        sb,
        org_id="org-1",
        actor_id=None,
        action="connector.auth.failed",
        resource_type="connector",
        resource_id="c-1",
        metadata={"vendor": "hubspot"},
    )
    insert_row = sb.table.return_value.insert.call_args[0][0]
    assert insert_row["action"] == "connector.auth.failed"


def test_audit_fetch_rows_without_response_error_attr():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.routers.audit import _fetch_rows

    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.range.return_value = chain
    chain.execute.return_value = SimpleNamespace(
        data=[{"id": "log-1", "org_id": "org-1", "action": "test", "created_at": "2026-06-07T00:00:00+00:00"}]
    )
    client = MagicMock()
    client.table.return_value = chain
    rows = _fetch_rows(client, "org-1", None)
    assert len(rows) == 1
    assert rows[0]["action"] == "test"
