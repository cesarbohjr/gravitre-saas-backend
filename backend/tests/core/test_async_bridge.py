"""run_coro_sync must work with and without a running event loop."""
from __future__ import annotations

import asyncio

import pytest

from app.core.async_bridge import run_coro_sync


async def _add(a: int, b: int) -> int:
    await asyncio.sleep(0)
    return a + b


def test_run_coro_sync_without_running_loop():
    assert run_coro_sync(_add(2, 3)) == 5


@pytest.mark.asyncio
async def test_run_coro_sync_inside_running_loop():
    # This is the MSP agent-step failure class: sync handler under async FastAPI.
    assert run_coro_sync(_add(10, 7)) == 17
