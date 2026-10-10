"""A virtual-time asyncio loop so a multi-second voice conversation runs in milliseconds.

How it works:

- ``VirtualTimeLoop.time()`` returns a virtual clock instead of the OS clock.
- When the loop has nothing ready to run and would block in ``select()`` until
  its next timer, it jumps the virtual clock straight to that timer instead of
  sleeping. Real socket events are still polled first.
- While any ``run_in_executor`` / ``asyncio.to_thread`` job is in flight the
  clock does NOT advance: the loop waits for the thread in real time. Worker
  threads therefore take zero virtual time (the scripted delays are the only
  latency in the model). A thread that is still running after
  ``STUCK_THREAD_REAL_S`` of real time stops freezing the clock, so a hung
  thread cannot hang the bench.
- ``time.time``, ``time.monotonic`` and ``time.perf_counter`` (and their
  ``_ns`` forms) are patched process-wide to the same virtual clock while
  ``patched_time`` is active, because Pipecat and the voice code read them
  directly (bot-speaking detection, grace windows, stop-marker TTLs). Modules
  that imported ``monotonic`` by name at import time (``threading``, ``queue``)
  keep the real clock, which is what their internal waits need.

What this does not model: CPU time. Pipeline processing is instantaneous in
virtual time, so results show protocol/scheduling latency plus the scripted
provider delays, never Python overhead or a loaded event loop.
"""
from __future__ import annotations

import asyncio
import contextlib
import selectors
import time as _time_mod
from typing import Any, Iterator

STUCK_THREAD_REAL_S = 2.0
_REAL_TIME = _time_mod.time
_REAL_MONOTONIC = _time_mod.monotonic
_REAL_PERF = _time_mod.perf_counter
_REAL_TIME_NS = _time_mod.time_ns
_REAL_MONOTONIC_NS = _time_mod.monotonic_ns
_REAL_PERF_NS = _time_mod.perf_counter_ns


class VirtualClock:
    """Seconds since the clock was created; only ever moved by the loop."""

    def __init__(self) -> None:
        self.now = 0.0
        # Wall-clock anchor so time.time() still looks like an epoch timestamp.
        self.epoch = _REAL_TIME()
        self.mono_base = 1_000.0
        # Times a worker thread outlived STUCK_THREAD_REAL_S and the clock moved on anyway.
        self.stuck_thread_jumps = 0

    def advance(self, seconds: float) -> None:
        if seconds > 0:
            self.now += seconds


class _VirtualSelector:
    """Wraps the loop's selector: polls real events, otherwise jumps the clock."""

    def __init__(self, inner: selectors.BaseSelector, loop: "VirtualTimeLoop") -> None:
        self._inner = inner
        self._loop = loop

    def select(self, timeout: float | None = None) -> list[Any]:
        loop = self._loop
        if timeout is not None and timeout <= 0:
            return self._inner.select(0)
        if loop.pending_executor_jobs:
            # Wait for worker threads in real time; virtual time stands still.
            events = self._inner.select(0.02)
            if events:
                loop.stuck_since = None
                return events
            if loop.stuck_since is None:
                loop.stuck_since = _REAL_MONOTONIC()
            if _REAL_MONOTONIC() - loop.stuck_since < STUCK_THREAD_REAL_S:
                return []
            loop.stuck_thread_jumps += 1
            loop.clock.stuck_thread_jumps += 1
        loop.stuck_since = None
        events = self._inner.select(0)
        if events:
            return events
        if timeout is None:
            # No timers at all: only an external event can wake us.
            return self._inner.select(None)
        loop.clock.advance(timeout)
        return []

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class VirtualTimeLoop(asyncio.SelectorEventLoop):
    def __init__(self, clock: VirtualClock | None = None) -> None:
        super().__init__()
        self.clock = clock or VirtualClock()
        self.pending_executor_jobs = 0
        self.stuck_since: float | None = None
        self.stuck_thread_jumps = 0
        self._selector = _VirtualSelector(self._selector, self)  # type: ignore[assignment]

    def time(self) -> float:
        return self.clock.mono_base + self.clock.now

    def run_in_executor(self, executor: Any, func: Any, *args: Any) -> asyncio.Future[Any]:
        fut = super().run_in_executor(executor, func, *args)
        self.pending_executor_jobs += 1

        def _done(_f: asyncio.Future[Any]) -> None:
            self.pending_executor_jobs -= 1

        fut.add_done_callback(_done)
        return fut


@contextlib.contextmanager
def patched_time(clock: VirtualClock) -> Iterator[None]:
    """Point the ``time`` module's clocks at ``clock`` for the duration."""

    def _time() -> float:
        return clock.epoch + clock.now

    def _mono() -> float:
        return clock.mono_base + clock.now

    saved = (
        _time_mod.time,
        _time_mod.monotonic,
        _time_mod.perf_counter,
        _time_mod.time_ns,
        _time_mod.monotonic_ns,
        _time_mod.perf_counter_ns,
    )
    _time_mod.time = _time  # type: ignore[assignment]
    _time_mod.monotonic = _mono  # type: ignore[assignment]
    _time_mod.perf_counter = _mono  # type: ignore[assignment]
    _time_mod.time_ns = lambda: int(_time() * 1e9)  # type: ignore[assignment]
    _time_mod.monotonic_ns = lambda: int(_mono() * 1e9)  # type: ignore[assignment]
    _time_mod.perf_counter_ns = lambda: int(_mono() * 1e9)  # type: ignore[assignment]
    try:
        yield
    finally:
        (
            _time_mod.time,
            _time_mod.monotonic,
            _time_mod.perf_counter,
            _time_mod.time_ns,
            _time_mod.monotonic_ns,
            _time_mod.perf_counter_ns,
        ) = saved  # type: ignore[assignment]


def run_virtual(coro_factory: Any, *, clock: VirtualClock | None = None) -> Any:
    """Run ``coro_factory()`` to completion on a fresh virtual-time loop."""
    clock = clock or VirtualClock()
    loop = VirtualTimeLoop(clock)
    policy = asyncio.get_event_loop_policy()
    previous = getattr(getattr(policy, "_local", None), "_loop", None)
    try:
        with patched_time(clock):
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro_factory())
    finally:
        try:
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for task in pending:
                task.cancel()
            if pending:
                with patched_time(clock):
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            asyncio.set_event_loop(previous)
            loop.close()


def real_monotonic() -> float:
    return _REAL_MONOTONIC()
