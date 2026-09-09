"""Relay final user transcripts to the client on the Pipecat path.

``GravitreJsonAudioSerializer`` already knows how to emit
``{"type": "transcript", "final": true}`` from a ``TranscriptionFrame``, but it
never gets the chance: ``LLMUserAggregator`` consumes ``TranscriptionFrame``
upstream of ``transport.output()``, so the serializer never sees one. Measured in
production on 2026-09-08 — four live turns received zero ``transcript`` messages
of any kind.

The client-visible consequences all live in the ``kind === "transcript"`` branch
of ``use-voice-duplex-session.ts``, which therefore never ran on this path:
``onUserFinal`` never fired, presence never advanced to ``thinking``, and
``assistantTextRef`` was never reset at turn start (a cross-turn text-bleed
risk). Stored history was *not* affected — persistence is backend-driven, and the
400 most-recent ``conversation_messages`` rows paired 200 user / 200 assistant
with no empty user content.

``OutputTransportMessageUrgentFrame`` is used rather than re-pushing the
transcription itself: message frames pass through the aggregator untouched and
reach the serializer's existing passthrough, so no new client-side message
vocabulary is introduced.

Scope: **final transcripts only.** Relaying interim transcripts would also
activate the hook's interim branch, which calls ``bargeIn()`` whenever the agent
is speaking. Server-side Flux barge-in already covers that case, so relaying
interims would add a second, client-driven interrupt path — a behavior change
well beyond restoring the display. The provisional live caption stays absent
until that interaction is designed deliberately.
"""
from __future__ import annotations

from typing import Any

from pipecat.frames.frames import (
    Frame,
    OutputTransportMessageUrgentFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.core.logging import get_logger

logger = get_logger(__name__)


class TranscriptRelayProcessor(FrameProcessor):
    """Mirror each final ``TranscriptionFrame`` as a client transcript message.

    Placed immediately after ``stt`` so the frame is observed before any
    downstream processor can absorb it. Pass-through: the original frame still
    continues along the pipeline unchanged.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._relayed = 0

    @property
    def relayed_count(self) -> int:
        """Number of final transcripts mirrored to the client this session."""
        return self._relayed

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)

        # InterimTranscriptionFrame is a sibling of TranscriptionFrame (both derive
        # from TextFrame, verified against Pipecat 1.8.1), not a subclass, so this
        # isinstance check matches finals only. Direction is guarded so an
        # upstream-travelling frame is never mirrored.
        if direction != FrameDirection.DOWNSTREAM or not isinstance(
            frame, TranscriptionFrame
        ):
            return

        text = str(getattr(frame, "text", None) or "").strip()
        if not text:
            return

        self._relayed += 1
        await self.push_frame(
            OutputTransportMessageUrgentFrame(
                message={
                    "type": "transcript",
                    "text": text,
                    "final": True,
                    "user_id": str(getattr(frame, "user_id", None) or ""),
                }
            ),
            FrameDirection.DOWNSTREAM,
        )
