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
import functools
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    InterimTranscriptionFrame,
    InterruptionFrame,
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
    InterruptIntent,
    classify_interrupt_intent,
    classify_user_utterance,
    could_become_speech_stop,
    is_backchannel,
)

logger = get_logger(__name__)

# Bounded wait for a transcript before a still-unclassified, bot-speaking-
# overlapping turn start is forced to resolve as a real interruption (safe
# default: never let an unclassified utterance suppress agent audio
# indefinitely). Chosen to comfortably cover a short backchannel word's STT
# finalization time without adding perceptible extra latency to a genuine
# interruption - Phase 6 instruments the real, live distribution of this.
DEFAULT_GRACE_PERIOD_S = 0.6
# While the bot is talking, a start with no words yet keeps waiting up to this
# long before it counts as an interruption: the bot's own voice through a
# speaker trips the start detector before any transcript arrives.
MAX_WORDLESS_WAIT_WHILE_SPEAKING_S = 1.8

# While the brain is still working and nothing is playing, these never cancel
# the request in flight: hesitations, acknowledgements, presence checks and
# small talk. ("you there?" used to cancel the turn and get "Yes, I'm here!",
# and the original request never ran.)
_PRESENCE_RE = re.compile(
    r"(?i)^\s*(?:(?:hey|hi|hello|um+|uh+|hmm+|so|ok(?:ay)?)[,.!?\s]*)*"
    r"(?:hello|hey|hi|you\s+there|are\s+you\s+(?:still\s+)?there|still\s+there|anyone\s+there|"
    r"can\s+you\s+hear\s+me|still\s+(?:working|thinking)(?:\s+on\s+it)?|are\s+you\s+(?:working|thinking)|"
    r"take\s+your\s+time|no\s+rush|whenever)?[,.!?\s]*$"
)
_THINKING_HOLD_MAX_WORDS = 6


def is_hold_while_thinking(text: str) -> bool:
    """True when speech during the brain's thinking window must not cancel it."""
    stripped = (text or "").strip()
    if not stripped:
        return True
    if len(stripped.split()) > _THINKING_HOLD_MAX_WORDS:
        return False
    classification = classify_user_utterance(stripped)
    if classification in (
        BackchannelClassification.STOP_COMMAND,
        BackchannelClassification.CORRECTION,
    ):
        return False
    if is_backchannel(classification):
        return True
    if _PRESENCE_RE.match(stripped):
        return True
    from app.services.pipecat_voice.utterance_gate import is_filler_only

    if is_filler_only(stripped):
        return True
    try:
        from app.services.conversation_tier import _is_social_utterance

        return _is_social_utterance(stripped)
    except Exception:  # noqa: BLE001
        return False

# Interim text that is unambiguous enough to stop the bot before Flux finalizes.
_CLEAR_INTERRUPTIONS = frozenset(
    {
        BackchannelClassification.STOP_COMMAND,
        BackchannelClassification.CORRECTION,
        BackchannelClassification.NEW_QUESTION,
    }
)


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
        max_wordless_wait_s: float = MAX_WORDLESS_WAIT_WHILE_SPEAKING_S,
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
        self._max_wordless_wait_s = max(grace_period_s, max_wordless_wait_s)
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
        # The pending classification started while the brain was thinking
        # (generating, nothing playing) rather than while audio played.
        self._pending_thinking = False
        # A turn we opened without interruption and whose text we dropped:
        # later transcripts of the same utterance are dropped too while they
        # stay hold-worthy, so "you there?" never becomes a queued turn.
        self._held_turn = False
        self._held_text = ""
        self._held_thinking = False
        # voice_interrupt_intents_v1: the held utterance asked to silence
        # speech only ("stop talking, keep working").
        self._held_speech_stop = False
        # Latest interim text of the pending utterance (finals go to _buffer_text).
        self._interim_text = ""

    def _intents_enabled(self) -> bool:
        return bool(getattr(self._gravitre_settings, "voice_interrupt_intents_v1", False))

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
            self._held_turn = False
            self._held_text = ""
            self._held_speech_stop = False
            # The brain mid-turn with nothing playing is protected too: Pipecat
            # would otherwise cancel the in-flight request on any sound.
            thinking = not self._bot_speaking and self._assistant_thinking()
            if not self._bot_speaking and not thinking:
                # Nothing to protect; behave exactly like the stock strategy.
                return await super().process_frame(frame)
            await self._begin_pending_classification(thinking=thinking)
            return ProcessFrameResult.STOP

        if isinstance(frame, TranscriptionFrame) and self._held_turn and not self._pending:
            # The aggregator has already appended this text; drop it again
            # while the held utterance is still only filler / small talk, so
            # "you there?" never becomes a queued turn of its own.
            self._held_text = f"{self._held_text} {frame.text}".strip()
            if self._held_speech_stop:
                # A silenced reply's work keeps running only while the words
                # still ask for silence alone. "...and cancel it" (or any real
                # request) turns into an ordinary interruption after all.
                if classify_interrupt_intent(self._held_text) in (
                    InterruptIntent.SPEECH_STOP,
                    InterruptIntent.BACKCHANNEL,
                ):
                    await self.trigger_reset_aggregation()
                else:
                    self._held_turn = False
                    self._held_speech_stop = False
                    logger.info(
                        "voice_turn_taking_speech_stop_escalated text=%r", self._held_text[:80]
                    )
                    await self.broadcast_frame(InterruptionFrame)
                return ProcessFrameResult.CONTINUE
            still_hold = (
                is_hold_while_thinking(self._held_text)
                if self._held_thinking
                else is_backchannel(classify_user_utterance(self._held_text))
                or self._is_bot_echo(self._held_text)
                or (
                    self._intents_enabled()
                    and classify_interrupt_intent(self._held_text) is InterruptIntent.BACKCHANNEL
                )
            )
            if still_hold:
                await self.trigger_reset_aggregation()
            else:
                self._held_turn = False
            return ProcessFrameResult.CONTINUE

        if isinstance(frame, TranscriptionFrame) and self._pending:
            self._buffer_text = f"{self._buffer_text} {frame.text}".strip()
            classification = classify_user_utterance(self._buffer_text)
            # Resolve as soon as we have a CONFIDENT read - a real
            # classification (not the "no text yet" empty-string fallback).
            if self._buffer_text:
                await self._resolve(classification, resolved_by_timeout=False)
            return ProcessFrameResult.CONTINUE

        if isinstance(frame, InterimTranscriptionFrame) and self._pending:
            # Interim text is unstable, so it never decides "backchannel". It
            # can decide "real interruption" though: Flux only finalizes at end
            # of turn, so waiting for the final kept the bot talking over a
            # new request for the whole grace window.
            interim = f"{self._buffer_text} {frame.text}".strip()
            interim_class = classify_user_utterance(interim)
            if self._is_bot_echo(interim):
                return ProcessFrameResult.CONTINUE
            if self._intents_enabled() and interim:
                self._interim_text = interim
                if classify_interrupt_intent(interim) is InterruptIntent.SPEECH_STOP:
                    # "stop talking" is unambiguous: silence now, keep the work.
                    self._buffer_text = interim
                    await self._resolve(interim_class, resolved_by_timeout=False)
                    return ProcessFrameResult.CONTINUE
                if could_become_speech_stop(interim):
                    # "stop" may still become "stop talking, keep working";
                    # cancelling the work on the first word would be wrong.
                    return ProcessFrameResult.CONTINUE
            if interim and (
                interim_class in _CLEAR_INTERRUPTIONS
                or (not is_backchannel(interim_class) and len(interim.split()) > 3)
            ):
                self._buffer_text = interim
                await self._resolve(interim_class, resolved_by_timeout=False)
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

    def _is_bot_echo(self, text: str) -> bool:
        probe = getattr(self._voice_session, "is_echo_of_bot", None)
        if probe is None or not text:
            return False
        try:
            return bool(probe(text))
        except Exception:  # noqa: BLE001
            return False

    async def _silence_reply(self) -> bool:
        """Ask the interrupt reporter to silence the current reply. False: nothing silenced."""
        handler = getattr(self._voice_session, "speech_stop_handler", None)
        if not callable(handler):
            return False
        try:
            return bool(await handler())
        except Exception as exc:  # noqa: BLE001 - fall back to an ordinary interruption
            logger.warning("voice_turn_taking_speech_stop_failed error=%s", exc)
            return False

    def _assistant_thinking(self) -> bool:
        return bool(getattr(self._voice_session, "assistant_generating", False))

    async def _begin_pending_classification(self, *, thinking: bool = False):
        self._pending = True
        self._pending_thinking = thinking
        self._buffer_text = ""
        self._interim_text = ""
        self._pending_started_at = time.monotonic()
        await self._cancel_grace_task()
        self._grace_task = self.create_task(
            self._grace_timeout_handler(), f"{self}::backchannel_grace_window"
        )

    async def _grace_timeout_handler(self):
        try:
            await asyncio.sleep(self._grace_period_s)
            while (
                self._pending
                and (self._bot_speaking or self._pending_thinking)
                and (
                    (self._bot_speaking and not self._buffer_text)
                    or (
                        self._intents_enabled()
                        and not self._buffer_text
                        and could_become_speech_stop(self._interim_text)
                    )
                )
                and time.monotonic() - self._pending_started_at < self._max_wordless_wait_s
            ):
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            return
        if self._pending:
            # Timed out without a confident classification. Safe default:
            # treat as a real interruption, never suppress on ambiguity.
            if self._intents_enabled() and not self._buffer_text and self._interim_text:
                # Decide on the words heard so far: a bare "stop" stays a stop.
                self._buffer_text = self._interim_text
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
        if self._pending_thinking and is_hold_while_thinking(self._buffer_text):
            # Nothing is playing and the brain is mid-turn: a cough, "hmm" or
            # "you there?" must not cancel the request. Open the turn without
            # interrupting and drop its text (the deep/medium acknowledgement
            # already told the user we are working on it).
            logger.info(
                "voice_turn_taking_thinking_hold text=%r decision_latency_ms=%.1f resolved_by_timeout=%s",
                self._buffer_text[:80],
                decision_latency_ms,
                resolved_by_timeout,
            )
            await self.trigger_user_turn_started(
                enable_interruptions=False, enable_user_speaking_frames=False
            )
            if self._buffer_text:
                await self.trigger_reset_aggregation()
                self._held_turn = True
                self._held_text = self._buffer_text
                self._held_thinking = True
            return
        if self._buffer_text and self._is_bot_echo(self._buffer_text):
            # The mic heard the bot's own voice. Not the user: keep talking
            # and drop the text so it never becomes a turn of its own.
            logger.info(
                "voice_turn_taking_echo_ignored text=%r decision_latency_ms=%.1f",
                self._buffer_text[:80],
                decision_latency_ms,
            )
            await self.trigger_user_turn_started(
                enable_interruptions=False, enable_user_speaking_frames=False
            )
            await self.trigger_reset_aggregation()
            self._held_turn = True
            self._held_text = self._buffer_text
            self._held_thinking = False
            return
        backchannel = is_backchannel(classification)
        if (
            not backchannel
            and self._intents_enabled()
            and classify_interrupt_intent(self._buffer_text) is InterruptIntent.BACKCHANNEL
        ):
            # "mm-hmm" (normalized "mm hmm") is outside the closed set above.
            backchannel = True
            classification = BackchannelClassification.BACKCHANNEL
        if backchannel and self._voice_session is not None and self._voice_session.expects_answer():
            # The bot just asked something; "yes" / "sure" is the answer.
            backchannel = False
            classification = BackchannelClassification.INTERRUPTION

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

        if (
            not backchannel
            and self._intents_enabled()
            and classify_interrupt_intent(self._buffer_text) is InterruptIntent.SPEECH_STOP
            and await self._silence_reply()
        ):
            # "Stop talking (, keep working)": silence the reply, never cancel
            # the work. No interruption goes upstream, so the brain's turn and
            # its authorized tools keep running, and the words never become a
            # turn of their own.
            logger.info(
                "voice_turn_taking_speech_stop text=%r decision_latency_ms=%.1f",
                self._buffer_text[:80],
                decision_latency_ms,
            )
            await self.trigger_user_turn_started(
                enable_interruptions=False, enable_user_speaking_frames=False
            )
            await self.trigger_reset_aggregation()
            self._held_turn = True
            self._held_text = self._buffer_text
            self._held_thinking = False
            self._held_speech_stop = True
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
            self._held_turn = True
            self._held_text = self._buffer_text
            self._held_thinking = False
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
                # Audit write in a worker thread, not awaited: it is a blocking
                # Supabase insert and this runs while the bot is mid-sentence.
                asyncio.get_running_loop().run_in_executor(
                    None,
                    functools.partial(
                        record_interrupt_outcome,
                        settings,
                        org_id=org_id,
                        user_id=str(user_id) if user_id else None,
                        conversation_id=str(conversation_id) if conversation_id else None,
                        classification=classification,
                        text=self._buffer_text,
                        decision_latency_ms=decision_latency_ms,
                        resolved_by_timeout=resolved_by_timeout,
                    ),
                )
        except Exception:  # noqa: BLE001
            pass
