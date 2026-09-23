"""run_coro_sync must work with and without a running event loop."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.async_bridge import call_with_resource_retry, run_coro_sync


async def _add(a: int, b: int) -> int:
    await asyncio.sleep(0)
    return a + b


def test_run_coro_sync_without_running_loop():
    assert run_coro_sync(_add(2, 3)) == 5


@pytest.mark.asyncio
async def test_run_coro_sync_inside_running_loop():
    # This is the MSP agent-step failure class: sync handler under async FastAPI.
    assert run_coro_sync(_add(10, 7)) == 17


@pytest.mark.asyncio
async def test_run_coro_sync_sequential_hops_reuse_bridge_loop():
    """Second agent step must not spawn a new asyncio.run/thread pool (EAGAIN class)."""
    first = run_coro_sync(_add(1, 1))
    second = run_coro_sync(_add(2, 3))
    assert (first, second) == (2, 5)


@pytest.mark.asyncio
async def test_run_coro_sync_concurrent_hops_share_bridge_loop():
    async def _hop(n: int) -> int:
        await asyncio.sleep(0.01)
        return n

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda i: run_coro_sync(_hop(i)), range(3)))
    assert sorted(results) == [0, 1, 2]


def test_call_with_resource_retry_retries_eagain_once():
    calls = {"n": 0}

    def _flaky() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError(11, "Resource temporarily unavailable")
        return "ok"

    assert call_with_resource_retry(_flaky) == "ok"
    assert calls["n"] == 2
