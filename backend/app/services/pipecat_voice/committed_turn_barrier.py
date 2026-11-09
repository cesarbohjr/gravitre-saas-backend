"""Voice V2 commit barrier between speculative prefetch and the user aggregator.

Deepgram Flux may emit an EagerTranscriptionFrame with a provisional
ProposedUserStoppedSpeakingFrame before its authoritative final transcript.
The eager transcript can warm a scoped, read-only speculative computation, but
must never reach the user aggregator: it can otherwise start an assistant
response while the user is still talking.

Preserve normal frame order, except a provisional stop is held until the final
TranscriptionFrame. A resumed turn invalidates that pending stop. The original
final transcript and its stop proposal remain owned by Pipecat's turn strategy.
No provider call, tool action, approval or durable history mutation occurs here.
"""
from __future__ import annotations

from pipecat.frames.frames import (
    EagerEndOfTurnCancelFrame,
    EagerTranscriptionFrame,
    Frame,
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class CommittedTurnBarrierProcessor(FrameProcessor):
    """Never promote probable-EOT into an aggregator-owned committed user turn."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pending_stop: Frame | None = None
        self._awaiting_final = False
        self._suppressed_eager = 0

    @property
    def suppressed_eager_count(self) -> int:
        return self._suppressed_eager

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, EagerTranscriptionFrame):
            self._awaiting_final = True
            self._suppressed_eager += 1
            return

        if isinstance(frame, EagerEndOfTurnCancelFrame):
            # The speaker continued. Never replay a provisional stop.
            self._pending_stop = None
            self._awaiting_final = False
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, ProposedUserStartedSpeakingFrame):
            # A fresh utterance invalidates a stop from a previous candidate.
            self._pending_stop = None
            self._awaiting_final = False
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, ProposedUserStoppedSpeakingFrame) and self._awaiting_final:
            self._pending_stop = frame
            return

        if isinstance(frame, TranscriptionFrame):
            # Pipecat must receive authoritative words before resolving stop.
            await self.push_frame(frame, direction)
            if self._pending_stop is not None:
                pending = self._pending_stop
                self._pending_stop = None
                await self.push_frame(pending, direction)
            self._awaiting_final = False
            return

        await self.push_frame(frame, direction)
