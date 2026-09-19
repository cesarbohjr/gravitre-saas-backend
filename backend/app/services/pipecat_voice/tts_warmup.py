"""Silent ElevenLabs TTS WebSocket preconnect (no audible opener)."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


TTS_IDLE_EXPIRY_S = 45.0


def tts_idle_should_refresh(
    *,
    last_activity_monotonic: float | None,
    now_monotonic: float,
    idle_expiry_s: float = TTS_IDLE_EXPIRY_S,
    speaking: bool = False,
) -> bool:
    """Refresh a warm TTS socket after idle expiry — never mid-utterance."""
    if speaking:
        return False
    if last_activity_monotonic is None:
        return False
    return (now_monotonic - last_activity_monotonic) >= float(idle_expiry_s)


async def warm_elevenlabs_tts_connection(tts: Any) -> dict[str, Any]:
    """Open the ElevenLabs WS before the first speakable token.

    Does not send speakable text — avoids audible warm-up artifacts.
    """
    out: dict[str, Any] = {"ok": False, "method": "elevenlabs_ws_preconnect"}
    connect = getattr(tts, "_connect", None)
    if not callable(connect):
        out["error"] = "tts_missing__connect"
        return out
    try:
        await connect()
        out["ok"] = True
        logger.info("pipecat_tts_warmup_ok method=elevenlabs_ws_preconnect")
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{exc.__class__.__name__}:{exc}"[:240]
        logger.warning("pipecat_tts_warmup_failed error=%s", exc)
    return out
