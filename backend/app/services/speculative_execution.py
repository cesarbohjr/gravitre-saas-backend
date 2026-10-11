"""Speculative (dry-run) execution scope for the shared brain.

A voice speculative run calls the same ``execute_task_streaming`` as a confirmed
turn, on text the user has not finished saying. That path persists durable
state (conversation ``task_state``, the kernel's ``active_objective``, typed
memories, audit rows, cognitive traces) and can reach connector tools. None of
that may happen for words the user never confirmed.

This module is the one switch every durable writer checks. A speculative run
executes inside :func:`speculative_scope`; while the scope is open and not yet
adopted:

* deferrable writes (task state, objective, memory promotion, traces, audit
  rows, latency rows) are recorded on the scope instead of executed, in call
  order, and replayed by :meth:`SpeculativeScope.commit` only if the run is
  adopted. A discarded run simply drops them.
* non-deferrable side effects (connector WRITE invokes, approval staging or
  consumption) are refused with :class:`SpeculativeSideEffectBlocked`, and the
  scope is marked blocked so the run can never be adopted. The confirmed turn
  then redoes the work on the normal path.

Once a run is adopted the scope flips to pass-through: writes the still-running
producer makes after adoption go straight to the database (after any deferred
writes have been replayed, so ordering is preserved).

The scope lives in a ``ContextVar``: it follows the run's asyncio task, the
tasks it spawns, ``asyncio.to_thread`` and ``app.core.io_pool.run_io`` (both
copy the context). Code outside a speculative run sees ``None`` and behaves
exactly as before.
"""
from __future__ import annotations

import asyncio
import contextvars
import inspect
import threading
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.turn_cancellation import (
    bound_turn_cancellation,
    current_turn_cancellation,
)

logger = get_logger(__name__)


class SpeculativeSideEffectBlocked(RuntimeError):
    """A speculative run tried a side effect that cannot be deferred."""


@dataclass
class _Deferred:
    label: str
    factory: Callable[[], Any]
    blocking: bool  # sync callable that does blocking I/O (run off the loop)
    # The turn token of the work that deferred it. The write runs under it,
    # so a write fenced on cancellation (task_state) is dropped once that
    # turn is cancelled, even when the replay outlives the turn.
    cancellation: Any = None


@dataclass
class SpeculativeScope:
    """Side-effect ledger for one speculative run."""

    label: str = "voice_speculative"
    deferred: list[_Deferred] = field(default_factory=list)
    adopted: bool = False
    discarded: bool = False
    blocked_reason: str | None = None
    # Read-your-writes for conversation task_state while writes are deferred:
    # (conversation_id, org_id) -> merged task_state the run would have stored.
    task_state_overlay: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    _flushed: asyncio.Event | None = None
    # Most writes an unadopted run may defer; beyond it the run is blocked.
    max_deferred: int | None = None
    # True while commit() replays the deferred writes. The producer is already
    # running again, so its writes keep queueing behind the replay instead of
    # reaching the database ahead of older deferred ones.
    flushing: bool = False
    # Guards deferred/flushing: writers on worker threads can defer while the
    # replay is finishing on the event loop.
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    # Writes that reach the scope after the replay finished. One worker thread
    # drains them in call order, whichever thread or event loop deferred them,
    # and _late_idle lets wait_flushed() (on any loop) wait for it.
    _late: list[_Deferred] = field(default_factory=list, repr=False, compare=False)
    _late_draining: bool = field(default=False, repr=False, compare=False)
    _late_idle: threading.Event = field(default_factory=threading.Event, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._late_idle.set()

    # -- state -----------------------------------------------------------------
    @property
    def active(self) -> bool:
        """True while writes must not reach the database: speculating, or
        discarded (a straggler task the cancelled run spawned must not write
        either). Only adoption turns the scope into a pass-through."""
        return not self.adopted

    @property
    def blocked(self) -> bool:
        return self.blocked_reason is not None

    @property
    def deferred_labels(self) -> list[str]:
        return [d.label for d in self.deferred]

    def mark_blocked(self, reason: str) -> None:
        if self.blocked_reason is None:
            self.blocked_reason = reason
            logger.info("speculative_side_effect_blocked label=%s reason=%s", self.label, reason)

    # -- deferral --------------------------------------------------------------
    def defer(self, label: str, factory: Callable[[], Any], *, blocking: bool = False) -> None:
        if self.defer_queued(label, factory, blocking=blocking):
            return
        # The writer saw the scope during the replay but the replay has since
        # finished: nothing will drain the main queue again, so write now.
        self._write_late(
            _Deferred(label=label, factory=factory, blocking=blocking, cancellation=current_turn_cancellation())
        )

    def defer_queued(self, label: str, factory: Callable[[], Any], *, blocking: bool = False) -> bool:
        """Queue (or drop) the write without ever running it here.

        Returns False only when the run's replay has already finished, so the
        caller must write late via ``defer``. Never blocks on another write, so
        a writer may call it while holding its own lock.
        """
        if self.discarded:
            # The run was discarded: whatever it still tries to write is dropped.
            return True
        origin = current_turn_cancellation()
        with self._lock:
            if not self.adopted and self.max_deferred is not None and len(self.deferred) >= self.max_deferred:
                # Over budget: this run can no longer be adopted (its writes
                # would be incomplete), so nothing more is kept for it.
                over = True
            else:
                over = False
                if not self.adopted or self.flushing:
                    self.deferred.append(
                        _Deferred(label=label, factory=factory, blocking=blocking, cancellation=origin)
                    )
                    return True
        if over:
            self.mark_blocked("deferred_write_limit")
            return True
        return False

    def _write_late(self, item: _Deferred) -> None:
        with self._lock:
            self._late.append(item)
            if not self._late_draining:
                self._late_draining = True
                self._late_idle.clear()
                threading.Thread(target=self._drain_late, name="speculative-late-writes", daemon=True).start()
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # Worker thread: the writer would have written inline, so wait for it.
            self._late_idle.wait()

    def _drain_late(self) -> None:
        while True:
            with self._lock:
                if not self._late:
                    # Cleared under the lock, so a concurrent _write_late either
                    # appended before this check or starts a fresh drain.
                    self._late_draining = False
                    self._late_idle.set()
                    return
                item = self._late.pop(0)
            try:
                with bound_turn_cancellation(item.cancellation):
                    result = item.factory()
                    if inspect.isawaitable(result):
                        asyncio.run(result)
            except Exception as exc:  # noqa: BLE001 - same fail-open as the writers themselves
                logger.warning("speculative_late_write_failed label=%s error=%s", item.label, exc)

    @staticmethod
    async def _run_item(item: _Deferred) -> bool:
        try:
            with bound_turn_cancellation(item.cancellation):
                if item.blocking:
                    await asyncio.to_thread(item.factory)
                else:
                    result = item.factory()
                    if inspect.isawaitable(result):
                        await result
            return True
        except Exception as exc:  # noqa: BLE001 - same fail-open as the writers themselves
            logger.warning("speculative_deferred_write_failed label=%s error=%s", item.label, exc)
            return False

    async def wait_flushed(self) -> None:
        if self._flushed is not None:
            await self._flushed.wait()
        if not self._late_idle.is_set():
            await asyncio.to_thread(self._late_idle.wait)

    async def commit(self) -> int:
        """Adopt: replay every deferred write in order, outside the scope.

        Returns the number of writes replayed. Idempotent.
        """
        if not self.begin_commit():
            return 0
        return await self.replay()

    def begin_commit(self) -> bool:
        """Adopt now, synchronously; the replay itself runs in :meth:`replay`.

        From here on the run may do side effects (it is adopted), and its new
        durable writes queue behind the replay. Returns False when there is
        nothing to replay (already adopted, or discarded). Raises
        :class:`SpeculativeSideEffectBlocked` for a run that hit a refused
        side effect: its output must not be used at all.
        """
        if self.adopted or self.discarded:
            return False
        if self.blocked:
            # Never replay the writes of a run that hit a refused side effect.
            raise SpeculativeSideEffectBlocked(self.blocked_reason or "blocked")
        self._flushed = asyncio.Event()
        with self._lock:
            # Together, so a writer on another thread never sees "adopted and
            # not flushing" before the replay has even started.
            self.adopted = True
            self.flushing = True
        return True

    async def replay(self) -> int:
        """Replay the deferred writes after :meth:`begin_commit`."""
        token = _CURRENT.set(None)
        replayed = 0
        try:
            # Drain in order, including writes the producer queues meanwhile.
            while True:
                with self._lock:
                    if not self.deferred:
                        self.flushing = False
                        break
                    item = self.deferred.pop(0)
                if await self._run_item(item):
                    replayed += 1
        finally:
            _CURRENT.reset(token)
            with self._lock:
                self.flushing = False
            self.task_state_overlay.clear()
            self._flushed.set()
        return replayed

    def discard(self) -> int:
        """Drop every deferred write. Returns how many were dropped."""
        if self.adopted:
            return 0
        self.discarded = True
        dropped = len(self.deferred)
        self.deferred = []
        self.task_state_overlay.clear()
        return dropped


_CURRENT: contextvars.ContextVar[SpeculativeScope | None] = contextvars.ContextVar(
    "gravitre_speculative_scope", default=None
)


def current_scope() -> SpeculativeScope | None:
    """The scope deferrable writes must queue on, or None (confirmed work, or
    an adopted run whose deferred writes have all been replayed).

    While an adopted run's deferred writes are still being replayed, its new
    writes queue behind them so they land in call order.
    """
    scope = _CURRENT.get()
    if scope is None or not (scope.active or scope.flushing):
        return None
    return scope


def unadopted_scope() -> SpeculativeScope | None:
    """The scope only while the run is still unconfirmed. Refused side effects
    (connector writes, approvals) check this: an adopted run may do them."""
    scope = _CURRENT.get()
    if scope is None or not scope.active:
        return None
    return scope


def is_speculative() -> bool:
    return unadopted_scope() is not None


@contextmanager
def speculative_scope(scope: SpeculativeScope) -> Iterator[SpeculativeScope]:
    token = _CURRENT.set(scope)
    try:
        yield scope
    finally:
        _CURRENT.reset(token)


@contextmanager
def outside_speculation() -> Iterator[None]:
    """Run confirmed work from inside a speculative task (for example the
    previous turn's barge-in bookkeeping) with no scope applied."""
    token = _CURRENT.set(None)
    try:
        yield
    finally:
        _CURRENT.reset(token)


async def run_or_defer(label: str, factory: Callable[[], Awaitable[Any]]) -> tuple[bool, Any]:
    """Run an async durable write now, or defer it inside a speculative run.

    Returns ``(deferred, result)``. After adoption the write waits for the
    deferred replay to finish first so writes land in the original order.
    """
    raw = _CURRENT.get()
    if raw is not None and raw.active:
        raw.defer(label, factory)
        return True, None
    if raw is not None and raw.adopted:
        await raw.wait_flushed()
    return False, await factory()


def defer_if_speculative(label: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> bool:
    """Sync writers: record ``fn(*args, **kwargs)`` for replay and return True
    when inside an active speculative run; otherwise return False and let the
    caller write as usual.
    """
    scope = current_scope()
    if scope is None:
        return False
    scope.defer(label, lambda: fn(*args, **kwargs), blocking=True)
    return True


def bind_scope(coro: Any) -> Any:
    """Carry the caller's speculative scope into a coroutine that will run on
    another event loop (app.core.async_bridge), where the context is not
    inherited. Returns ``coro`` unchanged when no scope is set."""
    scope = _CURRENT.get()
    if scope is None:
        return coro

    async def _bound() -> Any:
        token = _CURRENT.set(scope)
        try:
            return await coro
        finally:
            _CURRENT.reset(token)

    return _bound()


def block_if_speculative(label: str) -> None:
    """Refuse a non-deferrable side effect (connector write, approval) while speculating."""
    scope = unadopted_scope()
    if scope is None:
        return
    scope.mark_blocked(label)
    raise SpeculativeSideEffectBlocked(f"speculative run may not perform {label}")
