"""Backchannel-aware user turn start strategy for the live Pipecat voice path.

Conversational-realism Phase 1 (real, live implementation - not a stub).

Pipecat's turn-taking model separates "propose a turn boundary" (a service
with its own turn detection, e.g. Deepgram Flux, emits
``ProposedUserStartedSpeakingFrame`` / ``ProposedUserStoppedSpeakingFrame``)
from "resolve the proposal into a decision"
(``ExternalUserTurnStartStrategy``/``ExternalUserTurnStopStrategy``, which emit
the real ``UserStartedSpeakingFrame``/``UserStoppedSpeakingFrame`` and broadcast
the interruption). The stock strategy resolves a start proposal immediately -
this is the confirmed, live root cause of the "agent stops on every uh-huh"
bug: there is no room to look at the words before cutting the agent off.

This module subclasses that resolver so that, ONLY when the bot is currently
speaking, a proposed user-turn-start is held open for a short, bounded grace
window instead of being resolved instantly. During that window we watch for
the utterance's transcript. As soon as we have enough to classify it (or the
window times out), we resolve:

  - BACKCHANNEL  -> the turn opens with interruptions AND UserStartedSpeaking
                     frames disabled, and the just-buffered text is dropped
                     from the LLM context via trigger_reset_aggregation() so
                     "uh-huh" never becomes a fake user message. Agent audio
                     is never touched.
  - anything else (STOP_COMMAND / CORRECTION / NEW_QUESTION / INTERRUPTION)
                  -> the turn opens normally, with the real interruption
                     broadcast exactly as it always was. Genuine interruptions
                     are unaffected other than the bounded classification
                     delay inherent to needing the words first.

When the bot is NOT speaking, this strategy is a pass-through to the stock
``ExternalUserTurnStartStrategy`` behavior - there is nothing to protect, so
no delay is introduced on the common case of a normal, non-overlapping turn.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    InterimTranscriptionFrame,
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
)
from pipecat.turns.types import ProcessFrameResult
from pipecat.turns.user_start.external_user_turn_start_strategy import (
    ExternalUserTurnStartStrategy,
)

from app.core.logging import get_logger
from app.services.pipecat_voice.backchannel_classifier import (
    BackchannelClassification,
    classify_user_utterance,
    is_backchannel,
)

logger = get_logger(__name__)

# Bounded wait for a transcript before a still-unclassified, bot-speaking-
# overlapping turn start is forced to resolve as a real interruption (safe
# default: never let an unclassified utterance suppress agent audio
# indefinitely). Chosen to comfortably cover a short backchannel word's STT
# finalization time without adding perceptible extra latency to a genuine
# interruption - Phase 6 instruments the real, live distribution of this.
DEFAULT_GRACE_PERIOD_S = 0.9


@dataclass
class BackchannelDecision:
    """One classified turn-start decision, for logging / Phase 6 metrics."""

    classification: BackchannelClassification
    text: str
    bot_was_speaking: bool
    decision_latency_ms: float
    resolved_by_timeout: bool


ClassificationCallback = Callable[[BackchannelDecision], Awaitable[None] | None]


class BackchannelAwareUserTurnStartStrategy(ExternalUserTurnStartStrategy):
    """Delays interruption on backchannel-shaped speech overlapping agent audio."""

    def __init__(
        self,
        *,
        enable_interruptions: bool = True,
        grace_period_s: float = DEFAULT_GRACE_PERIOD_S,
        on_classification: ClassificationCallback | None = None,
        gravitre_settings: Any | None = None,
        gravitre_org_id: str | None = None,
        gravitre_user_id: str | None = None,
        gravitre_conversation_id: str | None = None,
        voice_session: Any | None = None,
        **kwargs,
    ):
        super().__init__(enable_interruptions=enable_interruptions, **kwargs)
        self._grace_period_s = grace_period_s
        self._on_classification = on_classification
        self._gravitre_settings = gravitre_settings
        self._gravitre_org_id = gravitre_org_id
        self._gravitre_user_id = gravitre_user_id
        self._gravitre_conversation_id = gravitre_conversation_id
        self._voice_session = voice_session

        self._bot_speaking = False
        self._pending = False
        self._buffer_text = ""
        self._pending_started_at = 0.0
        self._grace_task = None

    async def cleanup(self):
        await self._cancel_grace_task()
        await super().cleanup()

    async def handle_user_turn_started(self):
        """A turn just opened (resolved by us or adopted elsewhere) - clear per-turn state."""
        await self._cancel_grace_task()
        self._pending = False
        self._buffer_text = ""
        await super().handle_user_turn_started()

    async def process_frame(self, frame: Frame) -> ProcessFrameResult:
        if isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
            if self._voice_session is not None:
                from app.services.pipecat_voice.voice_audio_origin import SPEAKING

                self._voice_session.set_turn_state(SPEAKING)
            return ProcessFrameResult.CONTINUE

        if isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            if self._voice_session is not None:
                from app.services.pipecat_voice.voice_audio_origin import LISTENING

                self._voice_session.set_turn_state(LISTENING)
            return ProcessFrameResult.CONTINUE

        if isinstance(frame, ProposedUserStartedSpeakingFrame):
            from app.services.pipecat_voice.voice_audio_origin import (
                SPEAKING,
                WARMING,
                get_session_origin,
                get_turn_state,
                should_drop_barge_in_broadcast,
            )

            origin = get_session_origin(self._voice_session)
            warming = bool(getattr(self._voice_session, "tts_warming", False))
            turn_state = get_turn_state(self._voice_session)
            if should_drop_barge_in_broadcast(
                origin=origin,
                turn_state=turn_state or (WARMING if warming else SPEAKING),
                bot_speaking=self._bot_speaking,
                tts_warming=warming,
                settings=self._gravitre_settings,
            ):
                # Probe/TTS echo during warmup or TTS: open the user turn for STT
                # without broadcasting InterruptionFrame.
                await self.trigger_user_turn_started(
                    enable_interruptions=False, enable_user_speaking_frames=True
                )
                return ProcessFrameResult.STOP
            if self._pending:
                # Already holding one open - don't restart the window.
                return ProcessFrameResult.STOP
            if not self._bot_speaking:
                # Nothing to protect; behave exactly like the stock strategy.
                return await super().process_frame(frame)
            await self._begin_pending_classification()
            return ProcessFrameResult.STOP

        if isinstance(frame, TranscriptionFrame) and self._pending:
            self._buffer_text = f"{self._buffer_text} {frame.text}".strip()
            classification = classify_user_utterance(self._buffer_text)
            # Resolve as soon as we have a CONFIDENT read - a real
            # classification (not the "no text yet" empty-string fallback).
            if self._buffer_text:
                await self._resolve(classification, resolved_by_timeout=False)
            return ProcessFrameResult.CONTINUE

        if isinstance(frame, InterimTranscriptionFrame) and self._pending:
            # Interim text is noisy/unstable - use it only as a liveness
            # signal (still speaking), never to resolve a final decision.
            return ProcessFrameResult.CONTINUE

        if isinstance(frame, ProposedUserStoppedSpeakingFrame) and self._pending:
            # The utterance is definitely over. Force a decision now with
            # whatever transcript we have rather than waiting out the full
            # grace window - short backchannel utterances end fast, and this
            # keeps the common case snappy.
            classification = classify_user_utterance(self._buffer_text)
            await self._resolve(classification, resolved_by_timeout=False)
            return ProcessFrameResult.CONTINUE

        if isinstance(frame, UserStartedSpeakingFrame):
            from app.services.pipecat_voice.voice_audio_origin import (
                SPEAKING,
                WARMING,
                get_session_origin,
                get_turn_state,
                should_drop_barge_in_broadcast,
            )

            origin = get_session_origin(self._voice_session)
            warming = bool(getattr(self._voice_session, "tts_warming", False))
            if should_drop_barge_in_broadcast(
                origin=origin,
                turn_state=get_turn_state(self._voice_session) or (WARMING if warming else SPEAKING),
                bot_speaking=self._bot_speaking,
                tts_warming=warming,
                settings=self._gravitre_settings,
            ):
                await self.trigger_user_turn_started(
                    enable_interruptions=False, enable_user_speaking_frames=True
                )
                return ProcessFrameResult.STOP
            return await super().process_frame(frame)

        return ProcessFrameResult.CONTINUE

    async def _begin_pending_classification(self):
        self._pending = True
        self._buffer_text = ""
        self._pending_started_at = time.monotonic()
        await self._cancel_grace_task()
        self._grace_task = self.create_task(
            self._grace_timeout_handler(), f"{self}::backchannel_grace_window"
        )

    async def _grace_timeout_handler(self):
        try:
            await asyncio.sleep(self._grace_period_s)
        except asyncio.CancelledError:
            return
        if self._pending:
            # Timed out without a confident classification. Safe default:
            # treat as a real interruption, never suppress on ambiguity.
            classification = classify_user_utterance(self._buffer_text)
            await self._resolve(classification, resolved_by_timeout=True)

    async def _cancel_grace_task(self):
        if self._grace_task is not None:
            task, self._grace_task = self._grace_task, None
            await self.cancel_task(task)

    async def _resolve(
        self, classification: BackchannelClassification, *, resolved_by_timeout: bool
    ):
        if not self._pending:
            return
        self._pending = False
        await self._cancel_grace_task()

        decision_latency_ms = (time.monotonic() - self._pending_started_at) * 1000.0
        backchannel = is_backchannel(classification)

        logger.info(
            "voice_turn_taking_classification classification=%s backchannel=%s "
            "text=%r decision_latency_ms=%.1f resolved_by_timeout=%s",
            classification.value,
            backchannel,
            self._buffer_text[:80],
            decision_latency_ms,
            resolved_by_timeout,
        )

        from app.services.pipecat_voice.voice_audio_origin import (
            SPEAKING,
            get_session_origin,
            should_suppress_interrupt,
        )

        if should_suppress_interrupt(
            origin=get_session_origin(self._voice_session),
            turn_state=SPEAKING,
            settings=self._gravitre_settings,
        ):
            await self.trigger_user_turn_started(
                enable_interruptions=False, enable_user_speaking_frames=False
            )
            return

        if backchannel:
            # Open the turn silently: no UserStartedSpeakingFrame, no
            # interruption. Then drop the buffered text from the LLM context
            # so "uh-huh" never becomes a fake user message that could kick
            # off an unwanted LLM turn while the agent is still talking.
            await self.trigger_user_turn_started(
                enable_interruptions=False, enable_user_speaking_frames=False
            )
            await self.trigger_reset_aggregation()
        else:
            await self.trigger_user_turn_started(
                enable_interruptions=self._enable_interruptions,
                enable_user_speaking_frames=True,
            )

        if self._on_classification is not None:
            decision = BackchannelDecision(
                classification=classification,
                text=self._buffer_text,
                bot_was_speaking=True,
                decision_latency_ms=decision_latency_ms,
                resolved_by_timeout=resolved_by_timeout,
            )
            result = self._on_classification(decision)
            if result is not None:
                await result
        try:
            from app.services.voice_interrupt_outcome import record_interrupt_outcome

            settings = getattr(self, "_gravitre_settings", None)
            org_id = str(getattr(self, "_gravitre_org_id", "") or "")
            user_id = getattr(self, "_gravitre_user_id", None)
            conversation_id = getattr(self, "_gravitre_conversation_id", None)
            if settings is not None and org_id:
                record_interrupt_outcome(
                    settings,
                    org_id=org_id,
                    user_id=str(user_id) if user_id else None,
                    conversation_id=str(conversation_id) if conversation_id else None,
                    classification=classification,
                    text=self._buffer_text,
                    decision_latency_ms=decision_latency_ms,
                    resolved_by_timeout=resolved_by_timeout,
                )
        except Exception:  # noqa: BLE001
            pass
