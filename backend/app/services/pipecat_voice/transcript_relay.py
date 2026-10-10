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

Backchannels. The relay sits before ``user_agg``, so it sees every final,
including the "yeah" / "mm-hm" said over the bot that the turn strategy then
drops (no interruption, text removed from the context). The browser treats any
final as the start of a new user turn: it cleared the reply on screen and
added a user message nobody sent. With a ``voice_session`` (Flux path, where
that strategy runs) each final is checked with the same predicates the strategy
uses and, when it will not become a turn, marked ``"backchannel": true`` with
the reason in ``"turn_taking"`` so the client can leave the reply alone.
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


def classify_non_turn_final(text: str, session: Any | None) -> str | None:
    """Why a final transcript will not become a user turn, or None if it will.

    Mirrors BackchannelAwareUserTurnStartStrategy: over bot speech, an echo of
    the bot or a backchannel (unless the bot just asked a question, when "yes"
    is the answer) is dropped; while the brain is thinking with nothing
    playing, hesitations, acknowledgements and presence checks are held.
    """
    if session is None or not text:
        return None
    try:
        bot_speaking = bool(getattr(session, "bot_speaking", False))
        generating = bool(getattr(session, "assistant_generating", False))
        if bot_speaking:
            if session.is_echo_of_bot(text):
                return "echo"
            from app.services.pipecat_voice.backchannel_classifier import (
                classify_user_utterance,
                is_backchannel,
            )

            if is_backchannel(classify_user_utterance(text)) and not session.expects_answer():
                return "backchannel"
            return None
        if generating:
            from app.services.pipecat_voice.backchannel_turn_strategy import (
                is_hold_while_thinking,
            )

            if is_hold_while_thinking(text):
                return "thinking_hold"
    except Exception:  # noqa: BLE001 - never lose a transcript over a label
        return None
    return None


class TranscriptRelayProcessor(FrameProcessor):
    """Mirror each final ``TranscriptionFrame`` as a client transcript message.

    Placed immediately after ``stt`` so the frame is observed before any
    downstream processor can absorb it. Pass-through: the original frame still
    continues along the pipeline unchanged.
    """

    def __init__(self, *, voice_session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._relayed = 0
        self._voice_session = voice_session

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
        message: dict[str, Any] = {
            "type": "transcript",
            "text": text,
            "final": True,
            "user_id": str(getattr(frame, "user_id", None) or ""),
        }
        reason = classify_non_turn_final(text, self._voice_session)
        if reason is not None:
            message["backchannel"] = True
            message["turn_taking"] = reason
        await self.push_frame(
            OutputTransportMessageUrgentFrame(message=message),
            FrameDirection.DOWNSTREAM,
        )
