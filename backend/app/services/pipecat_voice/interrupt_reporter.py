"""Track assistant text and report precise barge-in for ElevenLabs TTS.

Deepgram Speak v2 sendInterrupt/SpeakV2SpeechInterrupted applies only when TTS
is Deepgram Speak. Gravitre live TTS is ElevenLabs Flash over WebSocket, so we
emulate the useful contract: on InterruptionFrame, emit spoken_so_far vs
full_draft plus optional client playback_offset_ms.
"""
from __future__ import annotations

from typing import Any

from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    OutputTransportMessageUrgentFrame,
    TTSTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.core.logging import get_logger

logger = get_logger(__name__)


class ElevenLabsInterruptReporter(FrameProcessor):
    """Accumulate draft/spoken text; on interrupt publish speech.interrupted."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._draft = ""
        self._spoken_aligned = ""
        self._last_playback_offset_ms: float | None = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMFullResponseStartFrame):
            self._draft = ""
            self._spoken_aligned = ""
            self._last_playback_offset_ms = None
        elif isinstance(frame, LLMTextFrame):
            self._draft += str(getattr(frame, "text", None) or "")
        elif isinstance(frame, OutputTransportMessageUrgentFrame):
            msg = frame.message if isinstance(frame.message, dict) else {}
            if str(msg.get("type") or "") == "assistant_text":
                self._draft += str(msg.get("delta") or "")
        elif isinstance(frame, TTSTextFrame):
            self._spoken_aligned += str(getattr(frame, "text", None) or "")
        elif isinstance(frame, LLMFullResponseEndFrame):
            pass
        elif isinstance(frame, InterruptionFrame):
            offset = getattr(frame, "gravitre_playback_offset_ms", None)
            if offset is not None:
                try:
                    self._last_playback_offset_ms = float(offset)
                except (TypeError, ValueError):
                    self._last_playback_offset_ms = None
            spoken = (self._spoken_aligned or self._draft or "").strip()
            full = (self._draft or spoken).strip()
            payload = {
                "type": "speech.interrupted",
                "tts_provider": "elevenlabs",
                "speak_v2": False,
                "speak_v2_note": "N/A — live TTS is ElevenLabs, not Deepgram Speak v2",
                "spoken_text": spoken[:2000],
                "full_draft_text": full[:2000],
                "interrupted": True,
                "playback_offset_ms": self._last_playback_offset_ms,
            }
            logger.info(
                "pipecat_speech_interrupted spoken_chars=%s draft_chars=%s offset_ms=%s",
                len(spoken),
                len(full),
                self._last_playback_offset_ms,
            )
            await self.push_frame(
                OutputTransportMessageUrgentFrame(message=payload),
                direction,
            )
            # Clear so a follow-up turn starts clean.
            self._draft = ""
            self._spoken_aligned = ""
            self._last_playback_offset_ms = None

        await self.push_frame(frame, direction)
