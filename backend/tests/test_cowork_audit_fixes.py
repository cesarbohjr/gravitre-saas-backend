"""Tests for operator execute-action service."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.operator_execute_action_service import execute_operator_action


def test_execute_operator_action_follow_up_queues_job():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

    with patch("app.operators.agent_jobs.create_job") as create_job:
        create_job.return_value = {"id": "job-123"}
        result = execute_operator_action(
            client=client,
            org_id="org-1",
            user_id="user-1",
            environment="production",
            payload={
                "action_type": "immediate",
                "title": "Investigate sync failure",
                "description": "Review connector logs and retry",
            },
        )

    assert result["success"] is True
    assert result["entityType"] == "agent_job"
    assert result["entityId"] == "job-123"
    create_job.assert_called_once()


def test_weekly_workflow_totals_buckets():
    from app.routers.billing import _weekly_workflow_totals

    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value.data = [
        {"metric_type": "workflow_runs", "quantity": 10, "recorded_at": "2026-07-01T00:00:00+00:00"},
        {"metric_type": "workflow_runs", "quantity": 5, "recorded_at": "2026-07-08T00:00:00+00:00"},
    ]
    totals = _weekly_workflow_totals(client, "org-1", "2026-07-01T00:00:00+00:00")
    assert totals[0] == 10
    assert totals[1] == 5


def test_operator_action_workflow_uses_the_canonical_run_path():
    """A suggested action is a UI entry surface: it must start the same governed run
    (policy, approvals, queue) a manual run does, never a bare workflow_runs insert."""
    from app.services import operator_execute_action_service as svc

    client = MagicMock()
    with patch.object(svc, "_pick_workflow_id", return_value="wf-1"), patch(
        "app.routers.workflows._execute_workflow_with_context",
        return_value={"run_id": "run-9", "status": "pending_approval"},
    ) as canonical:
        result = execute_operator_action(
            client=client,
            org_id="org-1",
            user_id="user-1",
            environment="production",
            payload={"action_type": "immediate", "title": "Run weekly sync", "description": "workflow"},
            settings=MagicMock(),
        )

    canonical.assert_called_once()
    kwargs = canonical.call_args.kwargs
    assert kwargs["trigger_type"] == "manual" and kwargs["workflow_id"] == "wf-1" and kwargs["actor_id"] == "user-1"
    client.table.assert_not_called()
    assert result["entityId"] == "run-9"
    assert result["status"] == "pending_approval"
    assert "approval" in result["message"]
