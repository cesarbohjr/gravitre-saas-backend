"""Independent ElevenLabs TTS context cancel on barge-in.

Pipecat already closes the active audio context on InterruptionFrame. This
module is the Gravitre-owned contract: send ``close_context`` (or the vendor
interrupt hook) **without** tearing the session WebSocket. Reconnect-on-interrupt
(``InterruptibleTTSService._disconnect``) is forbidden here — that is a session
drop, not a context cancel.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

AUDIT_TTS_CONTEXT_CANCEL = "voice.tts.context_cancelled"


async def cancel_elevenlabs_tts_context(
    tts: Any,
    *,
    keep_session: bool = True,
) -> dict[str, Any]:
    """Stop the current synthesis context; keep the ElevenLabs WS if it is open."""
    result: dict[str, Any] = {
        "cancelled": False,
        "context_id": None,
        "method": None,
        "session_kept": True,
        "keep_session": bool(keep_session),
    }
    if tts is None:
        result["error"] = "tts_missing"
        return result

    ws_before = getattr(tts, "_websocket", None)
    context_id = None
    getter = getattr(tts, "get_active_audio_context_id", None)
    if callable(getter):
        try:
            context_id = getter()
        except Exception as exc:  # noqa: BLE001
            result["error"] = f"context_id:{exc.__class__.__name__}"
            return result
    if not context_id:
        turn_id = getattr(tts, "_turn_context_id", None)
        if turn_id:
            context_id = turn_id
    result["context_id"] = str(context_id) if context_id else None

    closer = getattr(tts, "_close_context", None)
    interrupted = getattr(tts, "on_audio_context_interrupted", None)
    try:
        if callable(closer) and context_id:
            await closer(context_id)
            result["cancelled"] = True
            result["method"] = "elevenlabs_close_context"
        elif callable(interrupted) and context_id:
            await interrupted(context_id)
            result["cancelled"] = True
            result["method"] = "on_audio_context_interrupted"
        else:
            result["method"] = "noop_no_active_context"
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{exc.__class__.__name__}:{exc}"[:240]
        logger.warning("pipecat_tts_context_cancel_failed error=%s", exc)

    if keep_session and ws_before is not None:
        ws_after = getattr(tts, "_websocket", None)
        result["session_kept"] = ws_after is ws_before
        if not result["session_kept"]:
            logger.warning("pipecat_tts_context_cancel_dropped_session")
    return result


def record_tts_context_cancel(
    settings: Any,
    *,
    org_id: str | None,
    user_id: str | None,
    conversation_id: str | None,
    result: dict[str, Any],
) -> None:
    if not settings or not org_id:
        return
    try:
        from app.services.pipecat_voice.voice_latency_metrics import _write

        payload = {
            k: result.get(k)
            for k in ("cancelled", "method", "session_kept", "keep_session")
        }
        _write(
            settings,
            org_id=org_id,
            user_id=user_id,
            conversation_id=conversation_id,
            action=AUDIT_TTS_CONTEXT_CANCEL,
            payload=payload,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("tts_context_cancel_audit_failed error=%s", exc)
