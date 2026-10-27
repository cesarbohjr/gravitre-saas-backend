"""Feature-gated, deterministic turn policy for live duplex speech.

The existing Pipecat strategy owns frame emission and task cancellation. This
controller owns only classification and bounded waiting policy: no I/O, no
provider calls, and no authority to approve or cancel work.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.pipecat_voice.backchannel_classifier import (
    BackchannelClassification,
    InterruptIntent,
    classify_interrupt_intent,
    classify_user_utterance,
    is_syntactically_incomplete,
)


class TurnAction(str, Enum):
    LISTEN = "listen"
    WAIT = "wait"
    BACKCHANNEL = "backchannel"
    INTERRUPT = "interrupt"
    SPEECH_ONLY_STOP = "speech_only_stop"
    PAUSE = "pause"


@dataclass(frozen=True)
class TurnDecision:
    action: TurnAction
    classification: BackchannelClassification
    reason: str


class ConversationalTurnControllerV2:
    """Pure decision layer, preserving existing interruption safety rules."""

    def decide(
        self,
        text: str,
        *,
        bot_speaking: bool,
        assistant_thinking: bool = False,
        final: bool = False,
        expects_answer: bool = False,
    ) -> TurnDecision:
        words = (text or "").strip()
        classification = classify_user_utterance(words)
        if not words:
            return TurnDecision(TurnAction.WAIT, classification, "no_transcript")
        intent = classify_interrupt_intent(words)
        if intent is InterruptIntent.SPEECH_STOP:
            return TurnDecision(TurnAction.SPEECH_ONLY_STOP, classification, "explicit_speech_stop")
        if intent is InterruptIntent.PAUSE:
            return TurnDecision(TurnAction.PAUSE, classification, "explicit_pause")
        if not final and is_syntactically_incomplete(words):
            # A trailing preposition or unfinished clause is not a completed
            # request. Never override explicit stop/pause instructions above.
            if classification not in (
                BackchannelClassification.STOP_COMMAND,
                BackchannelClassification.CORRECTION,
            ):
                return TurnDecision(TurnAction.WAIT, classification, "incomplete_interim")
        if (
            classification is BackchannelClassification.BACKCHANNEL
            and (bot_speaking or assistant_thinking)
            and not expects_answer
        ):
            return TurnDecision(TurnAction.BACKCHANNEL, classification, "acknowledgment")
        if classification is BackchannelClassification.BACKCHANNEL and expects_answer:
            return TurnDecision(TurnAction.INTERRUPT, BackchannelClassification.INTERRUPTION, "answer_expected")
        return TurnDecision(TurnAction.INTERRUPT, classification, "substantive_utterance")

    def hold_incomplete_interim(self, text: str, *, elapsed_s: float, max_wait_s: float) -> bool:
        """Bound the semantic hold; silence alone never authorizes an action."""
        decision = self.decide(text, bot_speaking=True, final=False)
        return (
            bool((text or "").strip())
            and decision.reason == "incomplete_interim"
            and elapsed_s < max_wait_s
        )
