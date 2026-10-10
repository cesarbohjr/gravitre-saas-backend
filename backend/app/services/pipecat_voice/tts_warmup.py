"""Silent ElevenLabs TTS WebSocket preconnect (no audible opener)."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

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


def tts_socket_open(tts: Any) -> bool:
    """Whether the TTS service's websocket is open (Pipecat ``websockets`` State.OPEN)."""
    ws = getattr(tts, "_websocket", None)
    if ws is None:
        return False
    state = getattr(ws, "state", None)
    name = getattr(state, "name", None) or str(state or "")
    return str(name).upper().endswith("OPEN")


class TtsIdleRefresher:
    """Keep the persistent ElevenLabs socket usable across long pauses.

    Pipecat's ElevenLabs service already sends a keepalive every 10 s, so a
    healthy socket stays open and is left alone: closing and reopening it
    would only add a handshake and a window in which a reply could start on a
    socket being torn down. What the keepalive cannot fix is a socket that the
    provider or the network already closed; the next reply would then pay the
    connect (run_tts reconnects lazily) on its critical path. After
    ``idle_expiry_s`` without TTS audio, and never while the bot is speaking
    or a reply is being generated, this reconnects such a socket silently.
    """

    def __init__(
        self,
        tts: Any,
        *,
        last_activity: Callable[[], float | None],
        busy: Callable[[], bool],
        idle_expiry_s: float = TTS_IDLE_EXPIRY_S,
        poll_s: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._tts = tts
        self._last_activity = last_activity
        self._busy = busy
        self._idle_expiry_s = float(idle_expiry_s)
        self._poll_s = float(poll_s)
        self._clock = clock
        self._started_at = clock()
        self._last_refresh: float | None = None
        self.refreshes = 0

    def _activity(self) -> float:
        marks = [self._started_at]
        try:
            last = self._last_activity()
        except Exception:  # noqa: BLE001
            last = None
        if last is not None:
            marks.append(float(last))
        if self._last_refresh is not None:
            marks.append(self._last_refresh)
        return max(marks)

    async def tick(self) -> dict[str, Any] | None:
        """One check; returns the warm-up result when it reconnected."""
        try:
            busy = bool(self._busy())
        except Exception:  # noqa: BLE001
            busy = True
        now = self._clock()
        if not tts_idle_should_refresh(
            last_activity_monotonic=self._activity(),
            now_monotonic=now,
            idle_expiry_s=self._idle_expiry_s,
            speaking=busy,
        ):
            return None
        if tts_socket_open(self._tts):
            # Healthy: the keepalive holds it. Restart the idle window.
            self._last_refresh = now
            return None
        self._last_refresh = now
        result = await refresh_elevenlabs_tts_connection(self._tts)
        self.refreshes += 1
        logger.info("pipecat_tts_idle_refresh ok=%s", bool(result.get("ok")))
        return result

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self._poll_s)
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.debug("pipecat_tts_idle_refresh_failed error=%s", exc)


async def refresh_elevenlabs_tts_connection(tts: Any) -> dict[str, Any]:
    """Tear down a dead TTS connection fully, then preconnect.

    Reconnecting through ``_connect`` alone is not enough after a clean close:
    the service's receive task has already ended but is still set, so
    ``_connect`` opens a socket and never starts a reader for it. ``_disconnect``
    clears the receive and keepalive tasks so ``_connect`` recreates both.
    """
    disconnect = getattr(tts, "_disconnect", None)
    if callable(disconnect):
        try:
            await disconnect()
        except Exception as exc:  # noqa: BLE001
            logger.debug("pipecat_tts_refresh_disconnect_failed error=%s", exc)
    result = await warm_elevenlabs_tts_connection(tts)
    result["method"] = "elevenlabs_ws_idle_refresh"
    return result


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
