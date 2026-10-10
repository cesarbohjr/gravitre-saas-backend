"""Client -> server playback reports on the voice websocket.

The browser sends, per reply id, how much of the reply's audio it received
and played, periodically while it plays and once more when playback is cut::

    {"type": "playback.progress", "reply_id": 7, "received_ms": 5120,
     "played_ms": 2380, "interrupted": true, "final": true, "reason": "interrupted"}

These never become pipeline frames. They update the socket's
``VoicePlaybackTracker``, which the interrupt reporter reads to cut the stored
assistant message to what was played. Everything else is handled by
``GravitreJsonAudioSerializer`` unchanged.
"""
from __future__ import annotations

import json
from typing import Any

from pipecat.frames.frames import Frame

from app.core.logging import get_logger
from app.services.pipecat_voice.json_audio_serializer import GravitreJsonAudioSerializer

logger = get_logger(__name__)

PLAYBACK_PROGRESS_TYPE = "playback.progress"


def handle_playback_report(data: str | bytes, tracker: Any | None) -> bool:
    """True when ``data`` was a playback report (handled or ignored), False otherwise."""
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError:
            return False
    # Audio messages are by far the most common inbound frame; skip parsing
    # anything that cannot be a report.
    if PLAYBACK_PROGRESS_TYPE not in data:
        return False
    try:
        msg = json.loads(data)
    except json.JSONDecodeError:
        return False
    if not isinstance(msg, dict) or str(msg.get("type") or "").strip().lower() != PLAYBACK_PROGRESS_TYPE:
        return False
    if tracker is not None:
        try:
            tracker.note_client_report(msg)
        except Exception:  # noqa: BLE001 - a malformed report must never break the socket
            logger.debug("pipecat_playback_report_ignored", exc_info=True)
    return True


class PlaybackReportingSerializer(GravitreJsonAudioSerializer):
    """``GravitreJsonAudioSerializer`` that also takes ``playback.progress`` reports."""

    def __init__(self, *, playback_tracker: Any | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._playback_tracker = playback_tracker

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if handle_playback_report(data, self._playback_tracker):
            return None
        return await super().deserialize(data)
