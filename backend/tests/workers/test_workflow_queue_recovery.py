"""Workflow queue ownership / ack behavior (unit-level; not Redis integration)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.workers import workflow_queue as wq


@pytest.mark.asyncio
async def test_fail_closed_enqueue_raises():
    settings = type("S", (), {"redis_url": "redis://x", "workflow_queue_fail_closed": True})()
    with patch.object(wq, "get_settings", return_value=settings):
        with patch.object(wq, "is_queue_available", return_value=True):
            with patch("redis.asyncio.from_url", side_effect=ConnectionError("down")):
                with pytest.raises(RuntimeError, match="fail-closed"):
                    await wq.enqueue_workflow_run('{"run_id":"r1"}')


@pytest.mark.asyncio
async def test_ack_uses_fenced_atomic_script():
    settings = type("S", (), {"redis_url": "redis://x", "workflow_queue_fail_closed": True})()
    client = AsyncMock()
    client.__aenter__.return_value = client
    with patch.object(wq, "get_settings", return_value=settings):
        with patch("redis.asyncio.from_url", return_value=client):
            await wq.acknowledge_workflow_run(wq._receipt("owner", '{"run_id":"r1"}'))
    client.eval.assert_awaited_once_with(wq._ACK, 3, wq.WORKFLOW_RUN_CLAIMS, wq.WORKFLOW_RUN_LEASES, wq.WORKFLOW_RUN_OWNERS, "owner", '{"run_id":"r1"}')
