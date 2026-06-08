"""STA-118: Cross-org delegated sub-tasks."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.cross_org_delegated_task_service import (
    DelegatedTaskError,
    accept_delegated_task,
    cancel_delegated_task,
    complete_delegated_task,
    delegate_task_to_partner,
    reject_delegated_task,
    start_delegated_task,
)


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])

    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[])
    mock.insert.return_value = insert_mock

    update_mock = MagicMock()
    update_mock.eq.return_value = update_mock
    update_mock.execute.return_value = MagicMock(data=[])
    mock.update.return_value = update_mock

    return mock


def _task_row(**overrides) -> dict:
    base = {
        "id": "task-1",
        "partnership_id": "partnership-1",
        "delegator_org_id": "org-a",
        "delegate_org_id": "org-b",
        "delegator_agent_id": None,
        "delegate_agent_id": None,
        "delegate_agent_job_id": None,
        "title": "Review subcontractor bid",
        "instructions": "Validate pricing sheet",
        "payload": {"bidId": "bid-99"},
        "parent_reference": {"type": "workflow_run", "id": "run-1"},
        "status": "pending_delegate",
        "result": None,
        "status_message": None,
        "sync_version": 1,
        "created_at": "2026-06-08T00:00:00+00:00",
        "updated_at": "2026-06-08T00:00:00+00:00",
        "accepted_at": None,
        "started_at": None,
        "completed_at": None,
        "rejected_at": None,
        "cancelled_at": None,
        "status_synced_at": "2026-06-08T00:00:00+00:00",
    }
    base.update(overrides)
    return base


@patch("app.services.cross_org_delegated_task_service.get_active_partnership")
@patch("app.services.cross_org_delegated_task_service.write_audit_event")
def test_delegate_task_requires_active_partnership(mock_audit, mock_partnership):
    mock_partnership.return_value = None
    client = MagicMock()
    client.table.side_effect = lambda name: _table([])

    with pytest.raises(DelegatedTaskError, match="Active B2B partnership"):
        delegate_task_to_partner(
            client,
            delegator_org_id="org-a",
            delegate_org_id="org-b",
            title="Site survey",
            delegator_user_id="user-a",
        )
    mock_audit.assert_not_called()


@patch("app.services.cross_org_delegated_task_service.get_active_partnership")
@patch("app.services.cross_org_delegated_task_service.write_audit_event")
def test_delegate_task_creates_pending_row(mock_audit, mock_partnership):
    mock_partnership.return_value = {"id": "partnership-1"}
    tasks = _table([])
    tasks.insert.return_value.execute.return_value = MagicMock(data=[_task_row()])
    client = MagicMock()
    client.table.side_effect = lambda name: tasks if name == "cross_org_delegated_tasks" else _table([])

    result = delegate_task_to_partner(
        client,
        delegator_org_id="org-a",
        delegate_org_id="org-b",
        title="Review subcontractor bid",
        delegator_user_id="user-a",
        instructions="Validate pricing sheet",
        payload={"bidId": "bid-99"},
    )
    assert result["status"] == "pending_delegate"
    assert result["delegateOrgId"] == "org-b"
    assert result["syncVersion"] == 1
    tasks.insert.assert_called_once()
    mock_audit.assert_called_once()


@patch("app.services.cross_org_delegated_task_service.write_audit_event")
def test_accept_delegated_task_requires_delegate_org(mock_audit):
    pending = _task_row()
    tasks = _table([pending])
    tasks.update.return_value.execute.return_value = MagicMock(
        data=[{**pending, "status": "accepted", "sync_version": 2}]
    )
    client = MagicMock()
    client.table.side_effect = lambda name: tasks if name == "cross_org_delegated_tasks" else _table([])

    with pytest.raises(DelegatedTaskError, match="delegate organization"):
        accept_delegated_task(client, org_id="org-a", task_id="task-1", actor_id="user-a")

    result = accept_delegated_task(client, org_id="org-b", task_id="task-1", actor_id="user-b")
    assert result["status"] == "accepted"
    mock_audit.assert_called_once()


@patch("app.services.cross_org_delegated_task_service.write_audit_event")
def test_complete_delegated_task_syncs_result(mock_audit):
    accepted = _task_row(status="in_progress", sync_version=2, started_at="2026-06-08T01:00:00+00:00")
    tasks = _table([accepted])
    tasks.update.return_value.execute.return_value = MagicMock(
        data=[
            {
                **accepted,
                "status": "completed",
                "result": {"approved": True},
                "sync_version": 3,
                "completed_at": "2026-06-08T02:00:00+00:00",
            }
        ]
    )
    client = MagicMock()
    client.table.side_effect = lambda name: tasks if name == "cross_org_delegated_tasks" else _table([])

    result = complete_delegated_task(
        client,
        org_id="org-b",
        task_id="task-1",
        actor_id="user-b",
        result={"approved": True},
    )
    assert result["status"] == "completed"
    assert result["result"] == {"approved": True}
    assert mock_audit.call_count == 2


@patch("app.services.cross_org_delegated_task_service.write_audit_event")
def test_cancel_delegated_task_only_delegator(mock_audit):
    pending = _task_row()
    tasks = _table([pending])
    tasks.update.return_value.execute.return_value = MagicMock(
        data=[{**pending, "status": "cancelled", "sync_version": 2}]
    )
    client = MagicMock()
    client.table.side_effect = lambda name: tasks if name == "cross_org_delegated_tasks" else _table([])

    with pytest.raises(DelegatedTaskError, match="delegator organization"):
        cancel_delegated_task(client, org_id="org-b", task_id="task-1", actor_id="user-b")

    result = cancel_delegated_task(client, org_id="org-a", task_id="task-1", actor_id="user-a")
    assert result["status"] == "cancelled"
    mock_audit.assert_called_once()


@patch("app.services.cross_org_delegated_task_service.write_audit_event")
def test_reject_and_start_lifecycle(mock_audit):
    pending = _task_row()
    tasks = _table([pending])
    tasks.update.return_value.execute.return_value = MagicMock(
        data=[{**pending, "status": "rejected", "sync_version": 2}]
    )
    client = MagicMock()
    client.table.side_effect = lambda name: tasks if name == "cross_org_delegated_tasks" else _table([])

    rejected = reject_delegated_task(
        client,
        org_id="org-b",
        task_id="task-1",
        actor_id="user-b",
        reason="Out of scope",
    )
    assert rejected["status"] == "rejected"

    accepted_row = _task_row(status="accepted", sync_version=2)
    tasks.execute.return_value = MagicMock(data=[accepted_row])
    tasks.update.return_value.execute.return_value = MagicMock(
        data=[{**accepted_row, "status": "in_progress", "sync_version": 3}]
    )
    started = start_delegated_task(client, org_id="org-b", task_id="task-1", actor_id="user-b")
    assert started["status"] == "in_progress"
