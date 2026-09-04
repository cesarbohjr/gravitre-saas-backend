"""Synthetic user-turn bookends for text ingress (smoke / hybrid FE).

Pipecat's user aggregator only runs the LLM after a user turn starts and stops.
Browser text ingress sends a finalized TranscriptionFrame without VAD audio, so
we emit UserStarted/Stopped around those frames (user_id=browser).
"""
from __future__ import annotations

from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class TextTurnKickProcessor(FrameProcessor):
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if (
            isinstance(frame, TranscriptionFrame)
            and bool(getattr(frame, "finalized", False))
            and str(getattr(frame, "user_id", "") or "") == "browser"
        ):
            await self.push_frame(UserStartedSpeakingFrame(), direction)
            await self.push_frame(frame, direction)
            await self.push_frame(UserStoppedSpeakingFrame(), direction)
            return
        await self.push_frame(frame, direction)
