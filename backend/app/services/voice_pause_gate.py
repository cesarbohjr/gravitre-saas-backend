"""Temporary pause ("hold on", "wait", "one sec") for a voice conversation.

Pause is not stop. Defined behavior:

* Speech stops at once (the reply is silenced, as for "stop talking"), and
  what was not heard yet is kept to be spoken on resume.
* The request and its work go on: reads and reasoning continue, nothing is
  cancelled and nothing is carried or re-run.
* A write that reaches its commit point while paused waits here, before the
  provider is called. "Go on" releases it; a cancel, or the pause expiring
  (``PAUSE_MAX_S``), refuses it, and the refusal is recorded like any stopped
  write, so it is reported truthfully and never sent later by surprise.
* The pause ends on resume ("go on", "continue", "I'm back"), on a cancel,
  stop or correction (which cancel the work), on a new request, or on expiry.
  An explanation ("why?") does not end it.
* A resume phrase never approves anything: "go ahead" said while paused
  resumes the readback, it does not answer it.

Process-local: a voice socket's turns and their tools run in its process.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)

PAUSE_MAX_S = 30.0
#: An expired pause keeps refusing writes until the next turn ends or resumes
#: it; this bounds how long that marker outlives a conversation that never
#: comes back.
EXPIRED_HOLD_S = 10 * 60.0
_POLL_S = 0.1

RESUMED = "resumed"
EXPIRED = "expired"
CANCELLED = "cancelled"
NOT_PAUSED = "not_paused"


@dataclass
class _Pause:
    started: float
    expires: float
    reply_id: int | None = None
    released: threading.Event = field(default_factory=threading.Event)
    ended_by: str | None = None


_lock = threading.Lock()
_pauses: dict[tuple[str, str], _Pause] = {}


def _key(org_id: str | None, conversation_id: str | None) -> tuple[str, str] | None:
    oid = str(org_id or "").strip()
    cid = str(conversation_id or "").strip()
    return (oid, cid) if oid and cid else None


def pause(
    org_id: str | None,
    conversation_id: str | None,
    *,
    reply_id: int | None = None,
    max_s: float = PAUSE_MAX_S,
) -> bool:
    key = _key(org_id, conversation_id)
    if key is None:
        return False
    now = time.monotonic()
    with _lock:
        current = _pauses.get(key)
        if current is not None and current.ended_by is None and current.expires > now:
            return True
        _pauses[key] = _Pause(started=now, expires=now + max_s, reply_id=reply_id)
    logger.info("voice_pause_started conversation_id=%s reply_id=%s", key[1], reply_id)
    return True


def _end(org_id: str | None, conversation_id: str | None, how: str) -> bool:
    key = _key(org_id, conversation_id)
    if key is None:
        return False
    with _lock:
        current = _pauses.pop(key, None)
    if current is None:
        return False
    current.ended_by = how
    current.released.set()
    logger.info(
        "voice_pause_ended conversation_id=%s how=%s held_ms=%d",
        key[1],
        how,
        int((time.monotonic() - current.started) * 1000),
    )
    return True


def resume(org_id: str | None, conversation_id: str | None) -> bool:
    """"Go on": a write waiting at its commit point proceeds."""
    return _end(org_id, conversation_id, RESUMED)


def end_pause(org_id: str | None, conversation_id: str | None, how: str = CANCELLED) -> bool:
    """The pause ends without a resume (cancel, stop, correction, new request): waiting writes are refused."""
    return _end(org_id, conversation_id, how)


def _expire_locked(key: tuple[str, str], current: _Pause, now: float) -> bool:
    """Mark ``current`` expired when its time is up. Caller holds ``_lock``.

    An expired pause is kept (not removed) so a write that reaches its
    commit point afterwards is still refused: only "go on" approves holding
    work. ``resume``/``end_pause`` remove it; so does ``EXPIRED_HOLD_S``.
    """
    if current.ended_by is None and current.expires > now:
        return False
    if current.ended_by is None:
        current.ended_by = EXPIRED
        current.released.set()
    if current.expires + EXPIRED_HOLD_S <= now:
        _pauses.pop(key, None)
    return True


def is_paused(org_id: str | None, conversation_id: str | None) -> bool:
    """Speech is paused now (false once the pause expired)."""
    key = _key(org_id, conversation_id)
    if key is None:
        return False
    with _lock:
        current = _pauses.get(key)
        if current is None:
            return False
        return not _expire_locked(key, current, time.monotonic())


def holds_writes(org_id: str | None, conversation_id: str | None) -> bool:
    """A write must stop at this conversation's pause: it is active, or it expired without a go-ahead."""
    key = _key(org_id, conversation_id)
    if key is None:
        return False
    with _lock:
        current = _pauses.get(key)
        if current is None:
            return False
        _expire_locked(key, current, time.monotonic())
        return key in _pauses


def wait_while_paused(
    org_id: str | None,
    conversation_id: str | None,
    *,
    cancelled: Callable[[], bool] | None = None,
) -> str:
    """Block a write at its commit point until the pause ends. Worker threads only.

    Returns RESUMED (go ahead), EXPIRED or CANCELLED (refuse), or NOT_PAUSED.
    """
    key = _key(org_id, conversation_id)
    if key is None:
        return NOT_PAUSED
    with _lock:
        current = _pauses.get(key)
        if current is None:
            return NOT_PAUSED
        if _expire_locked(key, current, time.monotonic()):
            return EXPIRED
    logger.info("voice_pause_write_waiting conversation_id=%s", key[1])
    while True:
        remaining = current.expires - time.monotonic()
        if remaining <= 0:
            with _lock:
                _expire_locked(key, current, time.monotonic())
            return current.ended_by or EXPIRED
        if current.released.wait(min(_POLL_S, remaining)):
            return RESUMED if current.ended_by == RESUMED else (current.ended_by or CANCELLED)
        if cancelled is not None and cancelled():
            return CANCELLED


def reset_for_tests() -> None:
    with _lock:
        for pause_ in _pauses.values():
            pause_.ended_by = CANCELLED
            pause_.released.set()
        _pauses.clear()
