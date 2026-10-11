"""Task-scoped cancellation for one voice turn's work.

The conversation stop marker (``chat_turn_cancel_service``) is shared by every
turn of a conversation, and it has to be released for the next turn to run: a
new confirmed turn, or a socket opening or closing, clears it. A worker thread
of a cancelled turn that has not reached its provider call yet (coroutine
cancellation cannot stop a running thread) would then see the marker gone and
commit.

A :class:`TurnCancellation` belongs to one turn's work only. It is bound in a
``ContextVar`` around that work, so it follows the turn's asyncio task, tasks
it spawns, ``asyncio.to_thread`` and ``run_io`` (both copy the context), and
the async bridge (:func:`bind_cancellation`). Once cancelled it stays
cancelled: a later turn gets a new token and never un-cancels an old one.
``is_stop_requested`` reports a cancelled bound token as a stop, so the write
gate, the ReAct loop and the unified loop all refuse to go on for it.

Process-local on purpose: a voice socket's turns and their tools run in that
socket's process. The Redis marker still covers the cross-worker case.
"""
from __future__ import annotations

import asyncio
import contextlib
import contextvars
import itertools
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_generation = itertools.count(1)


class TurnCancellation:
    """Cancel token for one turn's work. Cancelling is final."""

    __slots__ = ("_event", "_linked", "_lock", "_waiters", "generation", "reason")

    def __init__(self) -> None:
        self.generation = next(_generation)
        self._event = threading.Event()
        self._lock = threading.Lock()
        self.reason: str | None = None
        self._linked: list[TurnCancellation] = []
        self._waiters: list[tuple[asyncio.AbstractEventLoop, asyncio.Event]] = []

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self, reason: str) -> bool:
        """Cancel this turn's work. Returns True the first time only."""
        with self._lock:
            if self._event.is_set():
                return False
            self.reason = reason
            self._event.set()
            linked = list(self._linked)
            waiters, self._waiters = self._waiters, []
        logger.info("voice_turn_cancelled generation=%s reason=%s", self.generation, reason)
        for loop, waiter in waiters:
            with contextlib.suppress(RuntimeError):  # loop already closed
                loop.call_soon_threadsafe(waiter.set)
        for other in linked:
            other.cancel(reason)
        return True

    def waiter(self) -> asyncio.Event:
        """An event on the running loop, set when this token is cancelled."""
        event = asyncio.Event()
        with self._lock:
            if not self._event.is_set():
                self._waiters.append((asyncio.get_running_loop(), event))
                return event
        event.set()
        return event

    def link(self, other: TurnCancellation) -> None:
        """Make ``other`` (work this turn took over, such as an adopted
        speculative run) part of this turn: cancelling this cancels it."""
        with self._lock:
            if not self._event.is_set():
                self._linked.append(other)
                return
            reason = self.reason or "cancelled"
        other.cancel(reason)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        state = f"cancelled:{self.reason}" if self.cancelled else "live"
        return f"TurnCancellation(generation={self.generation}, {state})"


_CURRENT: contextvars.ContextVar[TurnCancellation | None] = contextvars.ContextVar(
    "gravitre_turn_cancellation", default=None
)


def current_turn_cancellation() -> TurnCancellation | None:
    return _CURRENT.get()


def current_turn_cancelled() -> bool:
    token = _CURRENT.get()
    return token is not None and token.cancelled


def superseded_write(label: str) -> bool:
    """True (and logged) when a mutable request-state write must be dropped.

    For writes that record what the user wants (task state, objectives,
    channel overrides, promoted memory): once the turn they came from is
    cancelled, they are obsolete and must not land, even from a late replay.
    Audit rows and records of effects that really happened never call this.
    """
    token = _CURRENT.get()
    if token is None or not token.cancelled:
        return False
    logger.info("superseded_write_dropped label=%s reason=%s", label, token.reason)
    return True


@contextmanager
def bound_turn_cancellation(token: TurnCancellation | None) -> Iterator[TurnCancellation | None]:
    reset = _CURRENT.set(token)
    try:
        yield token
    finally:
        _CURRENT.reset(reset)


def bind_cancellation(coro: Any) -> Any:
    """Carry the caller's token into a coroutine run on another event loop."""
    token = _CURRENT.get()
    if token is None:
        return coro

    async def _bound() -> Any:
        reset = _CURRENT.set(token)
        try:
            return await coro
        finally:
            _CURRENT.reset(reset)

    return _bound()
