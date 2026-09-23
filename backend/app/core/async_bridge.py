"""Run async coroutines from sync call sites safely.

Workflow step handlers are sync, but they are often invoked from an already
running event loop (async FastAPI routes, async workers). ``asyncio.run`` then
raises RuntimeError. Nested ``ThreadPoolExecutor`` + ``asyncio.run`` per step
also exhausts Railway thread/fd budget (EAGAIN / errno 11) on the second
agent step of an inline graph run.

A single dedicated bridge loop reuses one thread for every sync→async hop.
"""
from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

T = TypeVar("T")

_bridge_lock = threading.Lock()
_bridge_loop: asyncio.AbstractEventLoop | None = None
_bridge_ready = threading.Event()


def _bridge_loop_main() -> None:
    global _bridge_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _bridge_loop = loop
    _bridge_ready.set()
    loop.run_forever()


def _ensure_bridge_loop() -> asyncio.AbstractEventLoop:
    global _bridge_loop
    with _bridge_lock:
        loop = _bridge_loop
        if loop is not None and loop.is_running():
            return loop
        _bridge_ready.clear()
        thread = threading.Thread(
            target=_bridge_loop_main,
            name="gravitre-async-bridge",
            daemon=True,
        )
        thread.start()
    if not _bridge_ready.wait(timeout=5):
        raise RuntimeError("async bridge loop failed to start")
    loop = _bridge_loop
    if loop is None or not loop.is_running():
        raise RuntimeError("async bridge loop is not running")
    return loop


def run_coro_sync(coro: Coroutine[Any, Any, T], *, timeout: float | None = None) -> T:
    """Await ``coro`` from sync code; reuse one bridge loop when a loop is running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    bridge = _ensure_bridge_loop()
    future = asyncio.run_coroutine_threadsafe(coro, bridge)
    return future.result(timeout=timeout)


def is_resource_unavailable(exc: BaseException) -> bool:
    """True for errno 11 / EAGAIN, including wrapped HTTP/API errors."""
    current: BaseException | None = exc
    seen = 0
    while current is not None and seen < 6:
        if getattr(current, "errno", None) == 11:
            return True
        msg = str(current).lower()
        if "resource temporarily unavailable" in msg or "[errno 11]" in msg:
            return True
        current = current.__cause__ or current.__context__
        seen += 1
    return False


def call_with_resource_retry(fn: Callable[..., T], *args: Any, retries: int = 2, **kwargs: Any) -> T:
    """Retry on EAGAIN (Railway thread/fd exhaustion during sequential graph work)."""
    last: BaseException | None = None
    for attempt in range(retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last = exc
            if not is_resource_unavailable(exc) or attempt >= retries:
                raise
            time.sleep(0.5 * (attempt + 1))
    assert last is not None
    raise last
