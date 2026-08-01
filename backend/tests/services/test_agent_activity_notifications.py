"""Agent lifecycle notification helpers call emit_notification."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.agent_activity_notifications import (
    notify_agent_completed,
    notify_agent_needs_approval,
    notify_agent_started,
)
from app.services.notification_emitter import normalize_event_type


def test_event_type_aliases_for_agents():
    assert normalize_event_type("agent_started") == "run_started"
    assert normalize_event_type("agent_discovery") == "task_completed"
    assert normalize_event_type("agent_task_completed") == "task_completed"


@patch("app.services.notification_emitter.emit_notification", return_value="notif-1")
def test_notify_agent_started_emits_run_started(mock_emit):
    client = MagicMock()
    nid = notify_agent_started(
        client,
        org_id="org-1",
        user_id="user-1",
        agent_id="agent-1",
        job_id="job-1",
        title="Agent task queued",
        body="Queued: research",
        result_url="/agents/agent-1",
    )
    assert nid == "notif-1"
    mock_emit.assert_called_once()
    kwargs = mock_emit.call_args.kwargs
    assert kwargs["event_type"] == "run_started"
    assert kwargs["title"] == "Agent task queued"
    assert kwargs["entity_ref"]["entity_type"] == "agent_job"
    assert kwargs["entity_ref"]["entity_id"] == "job-1"


@patch("app.services.notification_emitter.emit_notification", return_value="notif-2")
def test_notify_agent_completed_uses_task_completed(mock_emit):
    client = MagicMock()
    notify_agent_completed(
        client,
        org_id="org-1",
        user_id="user-1",
        agent_id="agent-1",
        run_id="run-1",
        title="Agent task completed: step",
        body="Done",
    )
    assert mock_emit.call_args.kwargs["event_type"] == "task_completed"


@patch("app.services.notification_emitter.emit_notification", return_value="notif-3")
def test_notify_agent_needs_approval(mock_emit):
    client = MagicMock()
    notify_agent_needs_approval(
        client,
        org_id="org-1",
        user_id="user-1",
        job_id="job-9",
        title="Approval needed",
        body="Please review",
    )
    assert mock_emit.call_args.kwargs["event_type"] == "approval_needed"
    assert mock_emit.call_args.kwargs["entity_ref"]["result_url"] == "/approvals"
