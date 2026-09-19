"""3.0-C barge-in WRITE safety — no uncommitted WRITE after TRUE_INTERRUPT.

READs are not speculative-cancelled. The write gate still requires HMAC/approval;
this only maps conversation stop / barge-in onto ``interrupt_blocks_write_commit``.
"""
from __future__ import annotations

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


def raise_if_barge_in_blocks_invoke(ctx: Any, action: str) -> None:
    """Last-line invoke_tool defense: uncommitted WRITE after barge-in/stop."""
    if not conversation_stop_blocks_invoke(ctx, action):
        return
    from app.services.react_write_gate import WRITE_COMMIT_INTERRUPTED
    from app.services.tool_types import ToolValidationError

    raise ToolValidationError(
        "Stopped before sending. The write was not executed.",
        code=WRITE_COMMIT_INTERRUPTED,
    )


def mark_voice_barge_in_stop(
    *,
    org_id: str | None,
    conversation_id: str | None,
    settings: Any | None = None,
    user_id: str | None = None,
) -> bool:
    """Arm conversation stop so in-flight ReAct WRITEs see barge-in before commit."""
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

    ok = request_stop(oid, cid, settings=settings)
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
