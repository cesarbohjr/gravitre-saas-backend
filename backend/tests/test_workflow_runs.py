"""Workflow runs API regression tests (BUILD/INSIGHTS audit spec)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from tests.support.build_insights import authenticate, chain_mock, clear_overrides, client, table_client


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    clear_overrides()


@patch("app.routers.workflows.get_supabase_client")
def test_run_list_returns_real_data(mock_client):
    runs = [
        {
            "id": "run-1",
            "workflow_id": "wf-1",
            "run_type": "execute",
            "status": "completed",
            "approval_status": "not_required",
            "created_at": "2026-06-07T10:00:00+00:00",
            "environment": "production",
        }
    ]
    wf_chain = chain_mock(data=[{"id": "wf-1", "name": "sync-customers"}])
    runs_chain = chain_mock(data=runs, count=1)
    sb = table_client({"workflow_runs": runs_chain, "workflows": wf_chain, "workflow_defs": wf_chain})
    mock_client.return_value = sb
    authenticate()
    response = client.get("/api/runs")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["runs"][0]["workflowName"] == "sync-customers"


@patch("app.routers.workflows.get_supabase_client")
def test_auto_retry_updates_run_status(mock_client):
    run_id = uuid4()
    select_chain = chain_mock(data=[{"id": str(run_id), "status": "failed"}])
    update_chain = chain_mock(data=[{"id": str(run_id), "status": "running"}])
    sb = MagicMock()

    def _table(name: str):
        table = MagicMock()
        if name == "workflow_runs":
            table.select.return_value = select_chain
            table.update.return_value = update_chain
        return table

    sb.table.side_effect = _table
    mock_client.return_value = sb
    authenticate(as_admin=True)
    response = client.post(f"/api/runs/{run_id}/retry", json={})
    assert response.status_code == 200
    assert response.json()["success"] is True
    update_chain.execute.assert_called()


@patch("app.routers.workflows.get_supabase_client")
@patch("app.routers.workflows.list_workflows", return_value=[{"status": "active"}])
def test_run_stats_calculated_correctly(mock_list, mock_client):
    runs_chain = chain_mock(
        data=[
            {"id": "r1", "status": "completed", "created_at": "2026-06-07T10:00:00+00:00"},
            {"id": "r2", "status": "failed", "created_at": "2026-06-07T11:00:00+00:00"},
        ]
    )
    mock_client.return_value = table_client({"workflow_runs": runs_chain})
    authenticate()
    response = client.get("/api/workflows/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["totalRunsThisWeek"] == 2
    assert body["overallSuccessRate"] == 50.0


@patch("app.routers.workflows.get_supabase_client")
@patch("app.routers.workflows.list_workflows", return_value=[])
def test_global_stats_not_hardcoded(mock_list, mock_client):
    mock_client.return_value = table_client({"workflow_runs": chain_mock(data=[])})
    authenticate()
    response = client.get("/api/workflows/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["totalRunsThisWeek"] == 0
    assert body["overallSuccessRate"] is None
    assert body["total"] == 0
