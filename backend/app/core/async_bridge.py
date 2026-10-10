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
import concurrent.futures
import os
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
    # The bridge loop does not inherit this thread's context; keep a
    # speculative voice run's dry-run scope attached to the work it awaits.
    from app.services.speculative_execution import bind_scope

    future = asyncio.run_coroutine_threadsafe(bind_scope(coro), bridge)
    return future.result(timeout=timeout)


_background_lock = threading.Lock()
_background_loop: asyncio.AbstractEventLoop | None = None


def _ensure_background_loop() -> asyncio.AbstractEventLoop:
    """A loop of its own for fire-and-forget work scheduled from worker threads.

    Kept separate from the bridge loop: background coroutines often make
    blocking supabase-py calls, and on the bridge loop those would stall every
    ``run_coro_sync`` caller (workflow steps) queued behind them.
    """
    global _background_loop
    with _background_lock:
        loop = _background_loop
        if loop is not None and loop.is_running():
            return loop
        loop = asyncio.new_event_loop()
        ready = threading.Event()

        def _main() -> None:
            asyncio.set_event_loop(loop)
            loop.call_soon(ready.set)
            loop.run_forever()

        threading.Thread(target=_main, name="gravitre-background", daemon=True).start()
        if not ready.wait(timeout=5):
            raise RuntimeError("background loop failed to start")
        _background_loop = loop
        return loop


def cancel_background_tasks() -> int:
    """Cancel fire-and-forget tasks still pending on the background loop.

    Tests call this between cases so work spawned by one test can't pile up
    and keep making network calls for the rest of the run.
    """
    loop = _background_loop
    if loop is None or not loop.is_running():
        return 0

    async def _cancel_all() -> int:
        current = asyncio.current_task()
        pending = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
        for task in pending:
            task.cancel()
        return len(pending)

    future = asyncio.run_coroutine_threadsafe(_cancel_all(), loop)
    try:
        return future.result(timeout=1)
    except Exception:  # noqa: BLE001 - best effort; a blocked loop cancels once it frees up
        return 0


def spawn_background(coro: Coroutine[Any, Any, Any]) -> "asyncio.Future[Any] | asyncio.Task[Any]":
    """Fire-and-forget ``coro`` from sync or async code.

    On the event loop thread this is ``loop.create_task``. From a worker thread
    (sync ``def`` route handlers run in Starlette's threadpool, where
    ``asyncio.create_task`` raises "no running event loop") the coroutine is
    scheduled on a dedicated background loop instead, so background telemetry
    and learning writes keep happening whichever kind of handler called them.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None:
        return asyncio.create_task(coro)
    if os.environ.get("GRAVITRE_DROP_BACKGROUND_TASKS") == "1":
        # Tests: fire-and-forget work from worker threads would otherwise keep
        # calling the fake Supabase host for the rest of the session.
        coro.close()
        dropped: "asyncio.Future[Any]" = concurrent.futures.Future()  # type: ignore[assignment]
        dropped.cancel()
        return dropped
    from app.services.speculative_execution import bind_scope

    return asyncio.run_coroutine_threadsafe(bind_scope(coro), _ensure_background_loop())


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
