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
