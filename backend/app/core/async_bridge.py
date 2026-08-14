"""Run async coroutines from sync call sites safely.

Workflow step handlers are sync, but they are often invoked from an already
running event loop (async FastAPI routes, async workers). ``asyncio.run`` then
raises RuntimeError. This helper matches the proven pattern used by
intelligence_pack_tools and cognitive_entry_adapters.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


def run_coro_sync(coro: Coroutine[Any, Any, T], *, timeout: float | None = None) -> T:
    """Await ``coro`` from sync code; use a worker thread when a loop is running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result(timeout=timeout)
