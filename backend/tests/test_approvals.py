"""Approvals queue regression tests (BUILD/INSIGHTS audit spec)."""
from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from tests.support.build_insights import authenticate, chain_mock, clear_overrides, client, table_client


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    clear_overrides()


def _approvals_mocks():
    return patch.multiple(
        "app.routers.workflows",
        get_plan_for_org=lambda *_a, **_k: {"features": {"approvals": True}},
        require_feature=lambda *_a, **_k: None,
    )


@patch("app.routers.workflows.get_approval_counts", return_value=(0, False))
@patch("app.routers.workflows.get_supabase_client")
def test_approval_appears_in_queue(mock_client, _mock_counts):
    runs = [
        {
            "id": "run-1",
            "workflow_id": "wf-1",
            "created_at": "2026-06-07T10:00:00+00:00",
            "required_approvals": 1,
            "approval_status": "pending",
            "triggered_by": "user-1",
        }
    ]
    mock_client.return_value = table_client(
        {
            "workflow_runs": chain_mock(data=runs),
            "workflow_defs": chain_mock(data=[{"id": "wf-1", "name": "Weekly report"}]),
        }
    )
    with _approvals_mocks():
        authenticate()
        response = client.get("/api/approvals")
    assert response.status_code == 200
    approvals = response.json()["approvals"]
    assert len(approvals) == 1
    assert approvals[0]["id"] == "run-1"
    assert approvals[0]["title"] == "Weekly report"


@patch("app.routers.workflows.approve_run")
@patch("app.routers.workflows.get_supabase_client")
def test_approve_changes_status(mock_client, mock_approve):
    run_id = uuid4()

    async def _approve(*_args, **_kwargs):
        return {"run_id": str(run_id), "status": "pending_approval", "message": "Approval recorded"}

    mock_approve.side_effect = _approve
    mock_client.return_value = object()
    with _approvals_mocks():
        authenticate()
        response = client.post(f"/api/approvals/{run_id}/approve", json={})
    assert response.status_code == 200
    assert response.json()["message"] == "Approval recorded"


@patch("app.routers.workflows.reject_run")
@patch("app.routers.workflows.get_supabase_client")
def test_reject_changes_status(mock_client, mock_reject):
    run_id = uuid4()

    async def _reject(*_args, **_kwargs):
        return {"run_id": str(run_id), "status": "cancelled"}

    mock_reject.side_effect = _reject
    mock_client.return_value = object()
    with _approvals_mocks():
        authenticate()
        response = client.post(f"/api/approvals/{run_id}/reject", json={"comment": "Needs revision"})
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


@patch("app.services.execution_outcome.finalize_execution_outcome")
@patch("app.routers.workflows.emit_execute_rejected")
@patch("app.routers.workflows.insert_run_approval")
@patch("app.routers.workflows.get_user_role", return_value="admin")
@patch("app.routers.workflows.get_run_with_steps")
@patch("app.routers.workflows.get_supabase_client")
def test_reject_accepts_optional_reason(
    mock_client,
    mock_get_run,
    _mock_role,
    mock_insert,
    _mock_rejected,
    _mock_finalize,
):
    from app.routers import workflows as workflows_module

    run_id = uuid4()
    mock_get_run.return_value = {
        "run_type": workflows_module.RUN_TYPE_EXECUTE,
        "status": workflows_module.RUN_STATUS_PENDING_APPROVAL,
    }
    mock_client.return_value = table_client({"run_approvals": chain_mock(data=[])})
    with _approvals_mocks():
        authenticate()
        response = client.post(f"/api/approvals/{run_id}/reject", json={})
    assert response.status_code == 200
    mock_insert.assert_called_once()
