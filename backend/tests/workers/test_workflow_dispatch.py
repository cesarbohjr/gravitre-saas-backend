"""Workflow queue dispatch tests (STA-94)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.workflow_dispatch import try_enqueue_workflow_run


@pytest.mark.asyncio
async def test_try_enqueue_workflow_run_when_queue_disabled():
    settings = MagicMock()
    settings.workflow_queue_enabled = False
    client = MagicMock()
    queued = await try_enqueue_workflow_run(
        settings,
        client,
        org_id="org-1",
        workflow_id="wf-1",
        run_id="run-1",
    )
    assert queued is False


@pytest.mark.asyncio
async def test_try_enqueue_workflow_run_when_enabled():
    settings = MagicMock()
    settings.workflow_queue_enabled = True
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"settings": {}, "data_region": "us"}]
    )

    with patch("app.workers.workflow_dispatch.is_queue_available", return_value=True):
        with patch("app.workers.workflow_dispatch.enqueue_workflow_run", new_callable=AsyncMock) as enqueue:
            queued = await try_enqueue_workflow_run(
                settings,
                client,
                org_id="org-1",
                workflow_id="wf-1",
                run_id="run-1",
            )
    assert queued is True
    enqueue.assert_awaited_once()
