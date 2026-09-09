"""Dedicated thread pool for synchronous, blocking client I/O.

``asyncio.to_thread`` submits to the loop's *default* executor, which is sized
``min(32, cpu_count + 4)`` -- roughly 6 workers on a small container -- and is
shared with every other ``to_thread`` caller in the process.

Context assembly wants several blocking Supabase reads at once (org snapshot,
agent record, knowledge assignments, pack state, knowledge fabric, org bundle),
and one of them, ``org_context_service.get_snapshot``, spawns its own 5-thread
pool internally. Moving those reads off the event loop with ``to_thread`` fixed
the loop-blocking but moved the contention into that small shared pool:
``retrieval_gather`` went from a ~3.1s median to a ~5.0s median with samples as
high as 18.6s.

Giving these reads their own explicitly sized pool separates "not blocking the
event loop" from "competing for six shared workers". Size via
``IO_THREAD_POOL_SIZE``; the calls are network-bound and spend nearly all their
time blocked on a socket, so worker count is not bounded by CPU.
"""
from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, TypeVar

from app.core.logging import get_logger

logger = get_logger(__name__)

_T = TypeVar("_T")
_DEFAULT_SIZE = 32
_POOL: ThreadPoolExecutor | None = None


def _resolve_size() -> int:
    raw = (os.environ.get("IO_THREAD_POOL_SIZE") or "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return _DEFAULT_SIZE


def get_io_pool() -> ThreadPoolExecutor:
    """Process-wide pool for blocking I/O, created on first use."""
    global _POOL
    if _POOL is None:
        size = _resolve_size()
        _POOL = ThreadPoolExecutor(max_workers=size, thread_name_prefix="gravitre-io")
        cpus = os.cpu_count() or 1
        # The container's real worker budget could not be read over SSH (no key
        # on the deploy host), so record it here where it is observable.
        logger.info(
            "io_thread_pool_initialized max_workers=%s cpu_count=%s "
            "default_executor_would_be=%s",
            size,
            cpus,
            min(32, cpus + 4),
        )
    return _POOL


async def run_io(fn: Callable[..., _T], /, *args: Any, **kwargs: Any) -> _T:
    """Run a blocking callable off the event loop on the dedicated I/O pool.

    Drop-in for ``asyncio.to_thread`` that does not compete with the default
    executor.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(get_io_pool(), partial(fn, *args, **kwargs))
