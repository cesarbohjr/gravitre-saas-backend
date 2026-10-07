"""Event-triggered runs (webhook, HubSpot, Salesforce, Segment, PagerDuty) follow manual-run governance.

Before 2026-10-07 every event trigger created a run already "approved" with
required_approvals=0, so the canvas write gate blocked each write step: event
workflows could read but never write. They now resolve policy and the write
approval floor, and a workflow with writes opens a pending approval through the
same helper the canonical runner uses.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.event_triggered_runs import start_event_triggered_run

SETTINGS = SimpleNamespace(
    policy_allowed_envs="", policy_max_steps=0, policy_max_runtime_seconds=0, disable_connectors=False
)
READ_ONLY = {"schema_version": "v1", "steps": [{"id": "s1", "name": "Note", "type": "noop"}]}
WRITES = {"schema_version": "v1", "steps": [{"id": "s1", "name": "Tell the team", "type": "slack_post_message"}]}


async def _start(definition, *, policy=(0, []), execution=None):
    execution = execution or AsyncMock()
    execution.execute_workflow = AsyncMock(return_value=SimpleNamespace(status="completed"))
    with (
        patch("app.workflows.policy.resolve_policy", return_value=policy),
        patch("app.services.event_triggered_runs.create_execute_run", return_value={"id": "run-1"}) as create,
        patch("app.billing.service.get_plan_for_org", return_value={}),
        patch(
            "app.routers.workflows._open_pending_approval_run",
            return_value={"run_id": "run-p", "status": "pending_approval"},
        ) as pending,
    ):
        out = await start_event_triggered_run(
            SETTINGS,
            MagicMock(),
            org_id="org-1",
            workflow_id="wf-1",
            definition=definition,
            parameters={"event": "x"},
            actor_id="user-1",
            trigger_type="webhook",
            source="webhook_trigger",
            execution_service=execution,
        )
    return out, create, pending, execution


@pytest.mark.asyncio
async def test_read_only_event_workflow_runs_immediately():
    out, create, pending, execution = await _start(READ_ONLY)
    assert out == {"workflow_id": "wf-1", "run_id": "run-1", "status": "completed"}
    pending.assert_not_called()
    execution.execute_workflow.assert_awaited_once()


@pytest.mark.asyncio
async def test_event_workflow_with_writes_waits_for_approval_instead_of_failing():
    out, create, pending, execution = await _start(WRITES)
    assert out["status"] == "pending_approval" and out["run_id"] == "run-p"
    kwargs = pending.call_args.kwargs
    assert kwargs["required_approvals"] == 1 and kwargs["approval_floor_applied"] is True
    assert kwargs["trigger_type"] == "webhook"
    create.assert_not_called()
    execution.execute_workflow.assert_not_called()


@pytest.mark.asyncio
async def test_org_policy_requiring_approval_is_honoured_for_events():
    out, _, pending, execution = await _start(READ_ONLY, policy=(2, ["admin"]))
    assert out["status"] == "pending_approval"
    assert pending.call_args.kwargs["required_approvals"] == 2
    execution.execute_workflow.assert_not_called()


@pytest.mark.asyncio
async def test_policy_resolution_failure_fails_closed():
    from app.workflows.policy import PolicyResolutionError

    with patch("app.workflows.policy.resolve_policy", side_effect=PolicyResolutionError("db down")):
        out = await start_event_triggered_run(
            SETTINGS,
            MagicMock(),
            org_id="org-1",
            workflow_id="wf-1",
            definition=WRITES,
            parameters={},
            actor_id="user-1",
            trigger_type="hubspot",
            source="hubspot_trigger",
            execution_service=AsyncMock(),
        )
    assert out["status"] == "failed"
