"""Which voice connection owns a conversation, and what a new one recovers.

A browser that drops and reconnects opens a second socket on the same
conversation while the first one's work may still be running (a dropped
socket does not cancel an approved write that already reached its provider).
Three rules keep that safe:

* Ownership. The newest connection owns the conversation. Claiming it marks
  the older connection in this process ``superseded``: its speech and audio
  are no longer delivered and its client is told so. Its work still finishes
  and records its outcome (task_state, write effects), because cutting an
  approved write off mid-call would leave it neither sent nor safely unsent.
* Stop markers carry the connection token (``chat_turn_cancel_service``), so
  the old socket closing cannot clear a "cancel" the new connection armed.
* Recovery. A turn that reached a write and ended while its connection was
  gone or superseded leaves ``voice_undelivered_outcome`` in task_state. The
  next connection classifies the conversation's write as completed, failed,
  pending, cancelled, in progress or unknown from the existing records and
  tells the user once. Nothing is ever re-run: an unknown outcome goes
  through the existing reconcile-before-claim path if the user asks again.

The registry is process-local (a socket's turns run in its process); the
Redis key lets a connection on another worker see it was superseded.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

OWNER_TTL_SECONDS = 6 * 60 * 60
_KEY_PREFIX = "voice:conn:"

#: task_state key a connection leaves when a write outcome was not delivered.
UNDELIVERED_KEY = "voice_undelivered_outcome"

#: A claimed write younger than this is reported as still in progress; older
#: and still without an outcome, it is unknown (its worker may have died).
IN_PROGRESS_MAX_AGE_S = 120.0

COMPLETED = "completed"
FAILED = "failed"
PENDING = "pending"
CANCELLED = "cancelled"
IN_PROGRESS = "in_progress"
UNKNOWN = "unknown"
NOTHING = "none"

_DONE = frozenset({"executed", "completed", "verified"})
_FAILED = frozenset({"failed"})
_AWAITING = frozenset({"awaiting_confirm", "awaiting_params", "awaiting_admin_approval", "awaiting_user"})
_CLAIMED = frozenset({"executing", "claimed"})
_UNCERTAIN = frozenset({"outcome_uncertain", "awaiting_reconciliation"})
_CANCELLED = frozenset({"cancelled", "canceled", "withdrawn", "rejected"})


@dataclass
class _Holder:
    token: str
    session: Any
    on_superseded: Callable[[], Any] | None
    claimed_at: float
    #: Wall-clock claim time; the shared key carries it so a newer claim on
    #: another worker can be told apart from a stale value.
    claimed_wall: float = 0.0


_lock = threading.Lock()
_owners: dict[str, _Holder] = {}
# Older connections of a conversation still alive in this process.
_superseded: dict[str, list[_Holder]] = {}


def _key(org_id: str, conversation_id: str) -> str:
    return f"{org_id}:{conversation_id}"


def _owner_value(token: str, claimed_wall: float) -> str:
    return f"{token}@{int(claimed_wall * 1000)}"


def _parse_owner(value: Any) -> tuple[str, float]:
    """(token, claimed wall time) from the shared key; 0.0 when it carries none."""
    text = value.decode() if isinstance(value, bytes) else str(value)
    token, _, stamp = text.partition("@")
    try:
        return token, int(stamp) / 1000.0
    except ValueError:
        return token, 0.0


def _redis(settings: Any | None) -> Any | None:
    try:
        from app.config import get_settings
        from app.core.redis_client import get_redis_client

        return get_redis_client(settings or get_settings())
    except Exception:  # noqa: BLE001
        return None


def claim_conversation(
    org_id: str | None,
    conversation_id: str | None,
    session: Any,
    *,
    settings: Any | None = None,
    on_superseded: Callable[[], Any] | None = None,
) -> str | None:
    """Make ``session``'s connection the owner. Returns the previous owner's token."""
    oid = str(org_id or "").strip()
    cid = str(conversation_id or "").strip()
    token = str(getattr(session, "connection_token", "") or "")
    if not oid or not cid or not token:
        return None
    key = _key(oid, cid)
    with _lock:
        previous = _owners.get(key)
        holder = _Holder(token, session, on_superseded, time.monotonic(), claimed_wall=time.time())
        _owners[key] = holder
        if previous is not None and previous.token != token:
            _superseded.setdefault(key, []).append(previous)
            _superseded[key] = _superseded[key][-4:]
    redis = _redis(settings)
    previous_token = previous.token if previous is not None else None
    if redis is not None:
        try:
            old = redis.getset(_KEY_PREFIX + key, _owner_value(token, holder.claimed_wall))
            if old is not None and previous_token is None:
                previous_token = _parse_owner(old)[0]
            redis.expire(_KEY_PREFIX + key, OWNER_TTL_SECONDS)
        except Exception as exc:  # noqa: BLE001
            logger.debug("voice_connection_claim_redis_failed error=%s", exc)
    if previous is not None and previous.token != token:
        _supersede(previous)
    logger.info(
        "voice_connection_claimed conversation_id=%s superseded=%s", cid, bool(previous_token)
    )
    return previous_token


def _supersede(holder: _Holder) -> None:
    session = holder.session
    if session is not None:
        try:
            session.superseded = True
        except Exception:
            logger.debug("voice_connection_supersede_flag_failed", exc_info=True)
    if holder.on_superseded is not None:
        try:
            holder.on_superseded()
        except Exception:
            logger.debug("voice_connection_superseded_callback_failed", exc_info=True)


def is_current_connection(
    org_id: str | None,
    conversation_id: str | None,
    token: str | None,
    *,
    settings: Any | None = None,
) -> bool:
    """False once a newer connection claimed the conversation (any worker)."""
    oid = str(org_id or "").strip()
    cid = str(conversation_id or "").strip()
    if not oid or not cid or not token:
        return True
    key = _key(oid, cid)
    with _lock:
        holder = _owners.get(key)
    if holder is not None and holder.token != token:
        return False
    redis = _redis(settings)
    if redis is not None:
        try:
            value = redis.get(_KEY_PREFIX + key)
            if value is not None:
                owner, claimed_wall = _parse_owner(value)
                if owner == token:
                    return True
                if holder is None:
                    return False
                # Another token: a newer owner only if it claimed after us.
                # An older value is stale (our own claim never reached the
                # key), and must never silence the live connection.
                return claimed_wall <= holder.claimed_wall
        except Exception:
            logger.debug("voice_connection_owner_read_failed", exc_info=True)
    return True


def release_conversation(org_id: str | None, conversation_id: str | None, token: str | None) -> None:
    """Socket closed: forget it. Never removes a newer owner."""
    oid = str(org_id or "").strip()
    cid = str(conversation_id or "").strip()
    if not oid or not cid or not token:
        return
    key = _key(oid, cid)
    with _lock:
        holder = _owners.get(key)
        if holder is not None and holder.token == token:
            _owners.pop(key, None)
        older = [h for h in _superseded.get(key, []) if h.token != token]
        if older:
            _superseded[key] = older
        else:
            _superseded.pop(key, None)


def cancel_superseded_work(org_id: str | None, conversation_id: str | None, reason: str) -> float | None:
    """Cancel the uncommitted work of older connections in this process.

    Called when the user cancels on the replacement connection: the work the
    old connection is still running gets its turn token cancelled, so a write
    that has not committed is refused. A write that already committed is not
    undone (nothing can). Returns the earliest claim time of those connections
    (monotonic), for reading their write effects, or None.
    """
    oid = str(org_id or "").strip()
    cid = str(conversation_id or "").strip()
    if not oid or not cid:
        return None
    with _lock:
        holders = list(_superseded.get(_key(oid, cid), []))
    earliest: float | None = None
    for holder in holders:
        earliest = holder.claimed_at if earliest is None else min(earliest, holder.claimed_at)
        token = getattr(holder.session, "turn_cancellation", None)
        cancel = getattr(token, "cancel", None)
        if callable(cancel):
            try:
                cancel(reason)
            except Exception:
                logger.debug("voice_superseded_cancel_failed", exc_info=True)
    return earliest


def has_superseded_work(org_id: str | None, conversation_id: str | None) -> bool:
    """An older connection of this conversation is still running a turn in this process."""
    oid = str(org_id or "").strip()
    cid = str(conversation_id or "").strip()
    if not oid or not cid:
        return False
    with _lock:
        holders = list(_superseded.get(_key(oid, cid), []))
    return any(bool(getattr(h.session, "work_active", False)) for h in holders)


def reset_for_tests() -> None:
    with _lock:
        _owners.clear()
        _superseded.clear()


@dataclass(frozen=True)
class RecoveredOutcome:
    kind: str
    label: str = ""
    summary: str = ""
    #: True when the user has not been told yet (announce once).
    undelivered: bool = False

    @property
    def should_announce(self) -> bool:
        if self.kind in (UNKNOWN, IN_PROGRESS):
            return True
        return self.undelivered and self.kind in (COMPLETED, FAILED, CANCELLED)


def _parse_ts(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _label(pending: dict[str, Any]) -> str:
    result = pending.get("result") if isinstance(pending.get("result"), dict) else {}
    params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
    for source in (result, pending, params):
        for field in ("task_label", "title", "label"):
            value = str(source.get(field) or "").strip()
            if value:
                return value
    return ""


def classify_recovery(
    task_state: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> RecoveredOutcome:
    """What happened to the conversation's latest write, from existing records only."""
    state = task_state if isinstance(task_state, dict) else {}
    if state.get("_unavailable"):
        return RecoveredOutcome(NOTHING)
    marker = state.get(UNDELIVERED_KEY) if isinstance(state.get(UNDELIVERED_KEY), dict) else None
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else None
    if pending is None:
        if marker and str(marker.get("status") or "") in _CANCELLED:
            return RecoveredOutcome(CANCELLED, label=str(marker.get("label") or ""), undelivered=True)
        return RecoveredOutcome(NOTHING)
    status = str(pending.get("status") or "").strip().lower()
    label = _label(pending)
    result = pending.get("result") if isinstance(pending.get("result"), dict) else {}
    summary = str(result.get("body") or "").strip()
    undelivered = marker is not None
    if status in _DONE:
        return RecoveredOutcome(COMPLETED, label, summary, undelivered)
    if status in _FAILED:
        return RecoveredOutcome(FAILED, label, summary, undelivered)
    if status in _AWAITING:
        return RecoveredOutcome(PENDING, label, "", undelivered)
    if status in _CANCELLED:
        return RecoveredOutcome(CANCELLED, label, "", undelivered)
    if status in _UNCERTAIN:
        return RecoveredOutcome(UNKNOWN, label, "", True)
    if status in _CLAIMED:
        claimed = _parse_ts(pending.get("claimed_at"))
        clock = now or datetime.now(UTC)
        if claimed is not None and (clock - claimed).total_seconds() < IN_PROGRESS_MAX_AGE_S:
            return RecoveredOutcome(IN_PROGRESS, label, "", True)
        return RecoveredOutcome(UNKNOWN, label, "", True)
    return RecoveredOutcome(NOTHING)


def _named(label: str, fallback: str) -> str:
    text = (label or "").strip().rstrip(".")
    return f"\"{text}\"" if text else fallback


def recovery_line(outcome: RecoveredOutcome) -> str:
    """One spoken line telling the user what happened while they were away."""
    what = _named(outcome.label, "the action you approved")
    if outcome.kind == COMPLETED:
        return f"Before we got cut off, {what} went through."
    if outcome.kind == FAILED:
        detail = outcome.summary.strip()
        line = f"Before we got cut off, {what} didn't go through."
        return f"{line} {detail}" if detail and len(detail) < 200 else line
    if outcome.kind == CANCELLED:
        return f"Before we got cut off, I cancelled {what}, so nothing was sent."
    if outcome.kind == IN_PROGRESS:
        return f"{what[0].upper()}{what[1:]} is still going out. Ask me in a moment and I'll confirm it."
    if outcome.kind == UNKNOWN:
        return (
            f"We got cut off while {what} was being sent, and I can't confirm whether it went through. "
            "I won't send it again unless you ask me to check."
        )
    return ""


def undelivered_marker(*, status: str, label: str, connection: str) -> dict[str, Any]:
    return {
        "status": status,
        "label": label,
        "connection": connection,
        "at": datetime.now(UTC).isoformat(),
    }
