"""3.0-C barge-in WRITE safety — no uncommitted WRITE after TRUE_INTERRUPT.

READs are not speculative-cancelled. The write gate still requires HMAC/approval;
this only maps conversation stop / barge-in onto ``interrupt_blocks_write_commit``.
"""
from __future__ import annotations

import itertools
import threading
import time
from typing import Any

from app.core.logging import get_logger
from app.services.react_write_gate import interrupt_blocks_write_commit

logger = get_logger(__name__)

AUDIT_BARGE_IN_WRITE = "voice.barge_in.write_gate"
BARGE_IN_INTERRUPT = {
    "reason": "barge_in",
    "signal": "true_interrupt",
    "uncommitted_write": True,
}


def resolve_write_interrupt(
    *,
    interrupt: dict[str, Any] | None,
    stop_requested: bool = False,
) -> dict[str, Any] | None:
    """Fresh interrupt dict for the WRITE commit check (may differ from turn start)."""
    if interrupt_blocks_write_commit(interrupt):
        return interrupt if isinstance(interrupt, dict) else dict(BARGE_IN_INTERRUPT)
    if stop_requested:
        merged = dict(BARGE_IN_INTERRUPT)
        merged["source"] = "conversation_stop"
        return merged
    return interrupt if isinstance(interrupt, dict) else None


def action_is_mutating_write(action: str) -> bool:
    """Catalog write authority — do not treat READs as interruptible commits."""
    from app.connectors.action_catalog.f1_write_slice import is_f1_write_action
    from app.services.catalog_write_authority import invoke_action_requires_write_approval

    key = str(action or "").strip()
    if not key:
        return False
    if is_f1_write_action(key):
        return True
    return bool(invoke_action_requires_write_approval(key))


def conversation_stop_blocks_invoke(ctx: Any, action: str) -> bool:
    oid = str(getattr(ctx, "org_id", "") or "").strip()
    cid = str(getattr(ctx, "conversation_id", "") or "").strip()
    if not oid or not cid:
        return False
    if not action_is_mutating_write(action):
        return False
    from app.services.chat_turn_cancel_service import is_stop_requested

    return is_stop_requested(
        oid,
        cid,
        settings=getattr(ctx, "settings", None),
    )


def _turn_cancelled_blocks_invoke(action: str) -> bool:
    from app.services.turn_cancellation import current_turn_cancelled

    return current_turn_cancelled() and action_is_mutating_write(action)


def raise_if_barge_in_blocks_invoke(ctx: Any, action: str) -> None:
    """Last-line invoke_tool defense: uncommitted WRITE after barge-in/stop.

    Also blocks a WRITE whose own turn was cancelled: a write that runs on
    after its turn is cancelled (so its outcome is recorded) must not start.
    """
    if not conversation_stop_blocks_invoke(ctx, action) and not _turn_cancelled_blocks_invoke(action):
        return
    _note(ctx, action, STATUS_BLOCKED)
    from app.services.react_write_gate import WRITE_COMMIT_INTERRUPTED
    from app.services.tool_types import ToolValidationError

    raise ToolValidationError(
        "Stopped before sending. The write was not executed.",
        code=WRITE_COMMIT_INTERRUPTED,
    )


def raise_if_speculative_blocks_invoke(action: str) -> None:
    """No connector WRITE from a speculative (unconfirmed) voice run.

    READs stay allowed (side-effect free). A mutating invoke marks the run
    blocked, so it is never adopted, and fails like any refused write.
    """
    from app.services.speculative_execution import unadopted_scope

    scope = unadopted_scope()
    if scope is None or not action_is_mutating_write(action):
        return
    scope.mark_blocked(f"connector_write:{action}")
    from app.services.react_write_gate import WRITE_COMMIT_INTERRUPTED
    from app.services.tool_types import ToolValidationError

    raise ToolValidationError(
        "Not executed: the request was not confirmed yet.",
        code=WRITE_COMMIT_INTERRUPTED,
    )


def mark_voice_barge_in_stop(
    *,
    org_id: str | None,
    conversation_id: str | None,
    settings: Any | None = None,
    user_id: str | None = None,
    owner: str | None = None,
) -> bool:
    """Arm conversation stop so in-flight ReAct WRITEs see barge-in before commit.

    ``owner`` is the voice connection's token, so only that connection releases it.
    """
    oid = str(org_id or "").strip()
    cid = str(conversation_id or "").strip()
    if not oid or not cid:
        return False
    from app.services.chat_turn_cancel_service import request_stop

    if settings is None:
        try:
            from app.config import get_settings

            settings = get_settings()
        except Exception:  # noqa: BLE001
            settings = None

    ok = request_stop(oid, cid, settings=settings, owner=owner)
    if ok and settings and user_id:
        try:
            from app.services.pipecat_voice.voice_latency_metrics import _write

            _write(
                settings,
                org_id=oid,
                user_id=user_id,
                conversation_id=cid,
                action=AUDIT_BARGE_IN_WRITE,
                payload={"uncommitted_write": True, "reason": "barge_in"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("voice_barge_in_write_audit_failed error=%s", exc)
    logger.info(
        "voice_barge_in_write_stop org_id=%s conversation_id=%s ok=%s",
        oid,
        cid,
        ok,
    )
    return ok


# --- Write effect ledger -----------------------------------------------------
#
# What a cancelled voice turn already did. Cancelling the voice turn's
# coroutine does not stop a connector call already running in a worker thread,
# and it never undoes one that finished, so "cancel it" is answered from what
# the tool layer recorded, not from what was cancelled. Process-local on
# purpose: a voice socket's tools run in that socket's process.

STATUS_STARTED = "started"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_UNCERTAIN = "uncertain"
STATUS_BLOCKED = "blocked"
TERMINAL_STATUSES = frozenset({STATUS_COMPLETED, STATUS_FAILED, STATUS_UNCERTAIN, STATUS_BLOCKED})

_EFFECT_TTL_S = 900.0
_EFFECTS_PER_CONVERSATION = 50
_effects_lock = threading.Lock()
_effects: dict[tuple[str, str], list[dict[str, Any]]] = {}
_effect_seq = itertools.count(1)


def _conversation_key(ctx: Any) -> tuple[str, str] | None:
    oid = str(getattr(ctx, "org_id", "") or "").strip()
    cid = str(getattr(ctx, "conversation_id", "") or "").strip()
    if not oid or not cid:
        return None
    return oid, cid


def _note(ctx: Any, action: str, status: str) -> dict[str, Any] | None:
    key = _conversation_key(ctx)
    if key is None:
        return None
    now = time.monotonic()
    entry: dict[str, Any] = {
        "id": next(_effect_seq),
        "action": str(action or ""),
        "status": status,
        "started_at": now,
        "updated_at": now,
    }
    with _effects_lock:
        rows = [row for row in _effects.get(key, []) if now - row["updated_at"] <= _EFFECT_TTL_S]
        rows.append(entry)
        _effects[key] = rows[-_EFFECTS_PER_CONVERSATION:]
    return entry


def begin_write_effect(ctx: Any, action: str) -> dict[str, Any] | None:
    """Right before a WRITE reaches the provider: check the stop again, then record it.

    The first check in ``invoke_tool`` runs before preflight, rate limits and
    permission reads; a barge-in that lands in between is caught here, at the
    last point before the provider call. Returns a handle for
    :func:`finish_write_effect`, or None for a READ or a call with no
    conversation.
    """
    if _conversation_key(ctx) is None or not action_is_mutating_write(action):
        return None
    raise_if_barge_in_blocks_invoke(ctx, action)
    _wait_if_paused(ctx, action)
    return _note(ctx, action, STATUS_STARTED)


def _wait_if_paused(ctx: Any, action: str) -> None:
    """The user said "hold on": the write waits here until "go on" (voice_pause_gate).

    Refused (and recorded as stopped) when the pause is cancelled or expires.
    Never blocks the event loop: a write reaching this point on the loop
    thread while paused is refused rather than waited for.
    """
    from app.services import voice_pause_gate

    key = _conversation_key(ctx)
    if key is None or not voice_pause_gate.is_paused(*key):
        return
    import asyncio

    try:
        asyncio.get_running_loop()
        on_loop = True
    except RuntimeError:
        on_loop = False
    outcome = (
        voice_pause_gate.CANCELLED
        if on_loop
        else voice_pause_gate.wait_while_paused(
            *key, cancelled=lambda: _turn_cancelled_blocks_invoke(action)
            or conversation_stop_blocks_invoke(ctx, action)
        )
    )
    if outcome in (voice_pause_gate.RESUMED, voice_pause_gate.NOT_PAUSED):
        # Resumed: the stop may have been armed meanwhile ("go on... no, cancel it").
        raise_if_barge_in_blocks_invoke(ctx, action)
        return
    _note(ctx, action, STATUS_BLOCKED)
    from app.services.react_write_gate import WRITE_COMMIT_INTERRUPTED
    from app.services.tool_types import ToolValidationError

    raise ToolValidationError(
        "Paused before sending, and the pause ended without a go-ahead. The write was not executed.",
        code=WRITE_COMMIT_INTERRUPTED,
    )


def finish_write_effect(handle: dict[str, Any] | None, status: str) -> None:
    if handle is None:
        return
    with _effects_lock:
        handle["status"] = status if status in TERMINAL_STATUSES else STATUS_UNCERTAIN
        handle["updated_at"] = time.monotonic()


def write_effects_since(
    org_id: str | None, conversation_id: str | None, since: float
) -> list[dict[str, Any]]:
    """Copies of this conversation's WRITE effects recorded at or after ``since`` (monotonic)."""
    oid = str(org_id or "").strip()
    cid = str(conversation_id or "").strip()
    if not oid or not cid:
        return []
    with _effects_lock:
        return [dict(row) for row in _effects.get((oid, cid), []) if row["started_at"] >= since]


def reset_write_effects_for_tests() -> None:
    with _effects_lock:
        _effects.clear()
