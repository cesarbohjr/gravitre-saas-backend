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
async def test_ack_removes_from_processing_list():
    settings = type("S", (), {"redis_url": "redis://x", "workflow_queue_fail_closed": False})()
    client = AsyncMock()
    client.lrem = AsyncMock()
    client.aclose = AsyncMock()
    with patch.object(wq, "get_settings", return_value=settings):
        with patch.object(wq, "is_queue_available", return_value=True):
            with patch("redis.asyncio.from_url", return_value=client):
                await wq.acknowledge_workflow_run('{"run_id":"r1"}')
    client.lrem.assert_awaited_once()
