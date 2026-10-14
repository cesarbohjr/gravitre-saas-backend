from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.operators  # noqa: F401 — load routers.workflows before patch targets resolve
import app.routers.workflows  # noqa: F401

from app.services.event_triggered_runs import _start_event_triggered_run


@pytest.mark.asyncio
async def test_auto_approved_run_uses_queue_when_enabled():
    settings = SimpleNamespace(
        event_trigger_use_workflow_queue=True,
        policy_allowed_envs="",
        policy_max_steps=0,
        policy_max_runtime_seconds=0,
        disable_connectors=False,
    )
    client = MagicMock()
    definition = {"schema_version": "v1", "steps": []}
    with (
        patch("app.workflows.policy.resolve_policy", return_value=(0, [])),
        patch("app.billing.service.get_plan_for_org", return_value={}),
        patch("app.services.event_triggered_runs.create_execute_run", return_value={"id": "run-1"}),
        patch(
            "app.workers.workflow_dispatch.try_enqueue_workflow_run",
            new=AsyncMock(return_value=True),
        ) as enqueue,
    ):
        out = await _start_event_triggered_run(
            settings,
            client,
            org_id="org-1",
            workflow_id="wf-1",
            definition=definition,
            parameters={},
            actor_id="user-1",
            trigger_type="freshservice.ticket",
            source="freshservice_test",
        )
    assert out == {"workflow_id": "wf-1", "run_id": "run-1", "status": "queued"}
    enqueue.assert_awaited_once()
