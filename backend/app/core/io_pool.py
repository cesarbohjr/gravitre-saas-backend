"""Dedicated thread pool for synchronous, blocking client I/O.

This pool exists for **isolation**, not for extra capacity. Be precise about why,
because the original justification for it was wrong.

``asyncio.to_thread`` submits to the loop's default executor, sized
``min(32, cpu_count + 4)``. This pool was introduced on the assumption that a
small container made that ~6 workers, and that moving context assembly's blocking
Supabase reads off the event loop had merely relocated the contention there --
``retrieval_gather`` had gone from a ~3.1s median to ~5.0s with an 18.6s sample.

Measured on the deploy target: ``cpu_count=48``, so the default executor was
already 32 workers -- the same width as this pool. Starvation was never the
cause, and after this pool shipped the median was ~4.1s with samples from 1.9s to
49.3s. That spread is environmental load, not pool width. The gather has not been
shown to improve.

What this pool does still buy: context reads cannot queue behind unrelated
``to_thread`` callers elsewhere in the process, and the width is explicit and
tunable via ``IO_THREAD_POOL_SIZE`` rather than derived from the host's CPU count.
The calls are network-bound and sit blocked on a socket, so worker count is not
bounded by CPU.
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
        # Kept because this log is what disproved the sizing rationale above:
        # it reported cpu_count=48 / default_executor_would_be=32 in production.
        logger.info(
            "io_thread_pool_initialized max_workers=%s cpu_count=%s "
            "default_executor_would_be=%s",
            size,
            cpus,
            min(32, cpus + 4),
        )
    return _POOL


def offload_enabled() -> bool:
    """Whether blocking calls are moved off the event loop.

    A/B switch, not a feature flag. Offloading was shipped on the strength of an
    argument rather than a measurement, and the latency claims made for it were
    later shown to rest on single samples. Setting
    ``VOICE_CONTEXT_IO_OFFLOAD=false`` restores the previous inline behaviour so
    the two can be compared with ``measure-voice-latency-harness.py --compare``.

    Defaults to on: not blocking the event loop is the correct behaviour on a
    voice server regardless of what the latency comparison says, because a
    blocked loop stalls audio frames for every concurrent session.
    """
    raw = (os.environ.get("VOICE_CONTEXT_IO_OFFLOAD") or "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


async def run_io(fn: Callable[..., _T], /, *args: Any, **kwargs: Any) -> _T:
    """Run a blocking callable off the event loop on the dedicated I/O pool.

    Drop-in for ``asyncio.to_thread`` that does not compete with the default
    executor.
    """
    if not offload_enabled():
        # Deliberately blocks the loop; the measurement baseline only.
        return fn(*args, **kwargs)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(get_io_pool(), partial(fn, *args, **kwargs))
