"""Track assistant text and report precise barge-in for ElevenLabs TTS.

Deepgram Speak v2 sendInterrupt/SpeakV2SpeechInterrupted applies only when TTS
is Deepgram Speak. Gravitre live TTS is ElevenLabs Flash over WebSocket, so we
emulate the useful contract: on InterruptionFrame, emit spoken_so_far vs
full_draft plus optional client playback_offset_ms.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
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


@dataclass(frozen=True)
class _InterruptedTurn:
    """Turn identity captured when the interruption happens.

    The durable writes run after the stop frame is already moving, so by the
    time they execute a new turn may have started and replaced the reporter's
    live fields. Everything they need is copied here first.
    """

    org_id: str | None
    user_id: str | None
    conversation_id: str | None
    user_text: str
    assistant_message_id: str | None


class ElevenLabsInterruptReporter(FrameProcessor):
    """Accumulate draft/spoken text; on interrupt publish speech.interrupted."""

    def __init__(
        self,
        *,
        reconcile_played_audio_enabled: bool = False,
        settings: Any | None = None,
        org_id: str | None = None,
        user_id: str | None = None,
        conversation_id: str | None = None,
        spoken_ledger: Any | None = None,
        tts_service: Any | None = None,
        speculative_coordinator: Any | None = None,
        voice_session: Any | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        # Two independent renderings of the SAME assistant turn arrive here: raw
        # token frames from the LLM, and the `assistant_text` deltas the Cognitive
        # LLM bridge emits for the browser (Phase 4 speakable chunks). Summing them
        # into one buffer doubles and interleaves the draft
        # ("Gravitre isGravitre.  the operator layer thatis the operator. …"),
        # which corrupts word alignment. Keep them apart and pick one.
        self._draft_llm = ""
        self._draft_client = ""
        self._spoken_aligned = ""
        self._last_playback_offset_ms: float | None = None
        self._reconcile_enabled = bool(reconcile_played_audio_enabled)
        # Populated by SpokenTextTapProcessor downstream of transport.output();
        # this processor cannot see TTSTextFrame itself (it sits upstream of tts).
        self._spoken_ledger = spoken_ledger
        self._settings = settings
        self._org_id = org_id
        self._user_id = user_id
        self._conversation_id = conversation_id
        self._tts_service = tts_service
        self._speculative_coordinator = speculative_coordinator
        self._voice_session = voice_session
        self._active_user_text = ""
        self._active_assistant_message_id: str | None = None
        # Barge-in side effects (stop marker, audit rows, durable reconcile) run
        # after the InterruptionFrame is pushed. The next turn waits on this
        # task before it clears the stop marker this socket armed.
        self._post_interrupt_tasks: set[asyncio.Task[Any]] = set()
        self._armed_stop: tuple[str, str] | None = None
        # Whether an assistant turn is live: the brain is still producing text
        # (LLMFullResponseStart..End) or the bot is still audibly speaking
        # (Bot*SpeakingFrame, which the output transport pushes upstream past
        # this processor). Flux opens every user turn with an InterruptionFrame,
        # including when the bot is idle. Treating those as barge-ins armed the
        # conversation stop marker on every turn, and the next answer (the
        # speculative run in particular) saw the marker and returned nothing.
        self._generating = False
        self._bot_speaking = False
        if voice_session is not None:
            voice_session.answer_expected = self.answer_expected

    @property
    def assistant_turn_live(self) -> bool:
        return (
            self._generating
            or self._bot_speaking
            or bool(self._draft_llm or self._draft_client)
        )

    def answer_expected(self) -> bool:
        """True when the reply ends in a question the listener has already heard."""
        draft = (self._draft_client or self._draft_llm or "").rstrip()
        if not draft.endswith("?"):
            return False
        body = draft[:-1]
        question_start = max(body.rfind(". "), body.rfind("! "), body.rfind("? "))
        question_start = question_start + 2 if question_start >= 0 else 0
        if self._spoken_ledger is not None and self._spoken_ledger.ever_recorded:
            # Playback has reached (roughly) the start of the question.
            return len(self._spoken_ledger.snapshot()) >= int(question_start * 0.9)
        return True

    @property
    def conversation_id(self) -> str | None:
        return self._conversation_id

    def begin_turn(self, user_text: str) -> None:
        self._active_user_text = str(user_text or "").strip()
        self._active_assistant_message_id = None

    def mark_turn_persisted(self, *, conversation_id: str | None, assistant_message_id: str | None) -> None:
        if conversation_id:
            self._conversation_id = conversation_id
        self._active_assistant_message_id = assistant_message_id or None

    def _snapshot_turn(self) -> _InterruptedTurn:
        return _InterruptedTurn(
            org_id=self._org_id,
            user_id=self._user_id,
            conversation_id=self._conversation_id,
            user_text=self._active_user_text,
            assistant_message_id=self._active_assistant_message_id,
        )

    async def _persist_interrupted_assistant_text(
        self, reconciled_text: str, turn: _InterruptedTurn | None = None
    ) -> None:
        """Persist the heard prefix without blocking the interruption transport."""
        turn = turn or self._snapshot_turn()
        if not self._settings or not turn.org_id or not turn.user_id:
            return
        try:
            persisted = await asyncio.to_thread(
                self._persist_interrupted_assistant_text_sync, reconciled_text, turn
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "pipecat_interrupted_history_reconcile_failed org_id=%s conversation_id=%s error=%s",
                turn.org_id, turn.conversation_id, str(exc),
            )
            return
        if persisted is None:
            return
        persisted_id, assistant_id = persisted
        # Adopt the ids only if no newer turn has replaced the one we persisted.
        if self._conversation_id in (None, turn.conversation_id):
            self._conversation_id = persisted_id
        if (
            self._active_user_text == turn.user_text
            and self._active_assistant_message_id in (None, turn.assistant_message_id)
        ):
            self._active_assistant_message_id = assistant_id

    def _persist_interrupted_assistant_text_sync(
        self, reconciled_text: str, turn: _InterruptedTurn
    ) -> tuple[str, str | None] | None:
        """Write the heard prefix for ``turn``. Returns (conversation_id, assistant_id) when it inserted."""
        from app.workflows.repository import get_supabase_client

        heard = reconciled_text.strip()
        client = get_supabase_client(self._settings)
        owned_current = False
        if turn.conversation_id:
            owned = (
                client.table("conversations")
                .select("id")
                .eq("id", turn.conversation_id)
                .eq("org_id", turn.org_id)
                .eq("user_id", turn.user_id)
                .limit(1)
                .execute()
            )
            owned_current = bool(getattr(owned, "data", None))
        message_id = str(turn.assistant_message_id or "").strip()

        def _update_exact() -> bool:
            updated = (
                client.table("conversation_messages").update({"content": heard})
                .eq("id", message_id)
                .eq("conversation_id", turn.conversation_id)
                .eq("role", "assistant")
                .execute()
            )
            return bool(getattr(updated, "data", None))

        if message_id and owned_current and _update_exact():
            return None
        # The stream can expose the stable assistant id before the durable
        # insert commits. If the row is not visible yet, fall through and
        # persist the active turn with that same id instead of silently
        # losing the heard prefix.

        # Mid-generation interruption: no completed assistant row exists yet.
        # Persist THIS active turn instead of ever rewriting "latest assistant",
        # which could belong to the previous turn.
        if not turn.user_text or not heard:
            return None
        from app.routers.assistant import _persist_conversation_turn
        persisted_id, assistant_id = _persist_conversation_turn(
            self._settings,
            org_id=turn.org_id,
            user_id=turn.user_id,
            conversation_id=turn.conversation_id,
            user_text=turn.user_text,
            assistant_text=heard,
            tool_results=[],
            assistant_message_id=message_id or None,
        )
        if persisted_id:
            return persisted_id, assistant_id
        # The insert lost a race: the completion writer committed this same
        # assistant id between our missed update and our insert, so the row now
        # holds the full draft including the tail nobody heard. Retry the exact
        # update once so the durable row matches what was played.
        if message_id and owned_current:
            _update_exact()
        return None

    def _run_post_interrupt_writes_sync(
        self,
        turn: _InterruptedTurn,
        *,
        tts_cancel: dict[str, Any] | None,
        reconcile_meta: dict[str, Any] | None,
        playback_offset_ms: float | None,
    ) -> bool:
        """Blocking barge-in bookkeeping. Runs in a worker thread, never on the loop.

        Returns whether a conversation stop marker was armed.
        """
        from app.services.voice_barge_in_write import mark_voice_barge_in_stop

        # First, so an in-flight ReAct write sees the barge-in as early as possible.
        armed = mark_voice_barge_in_stop(
            org_id=turn.org_id,
            conversation_id=turn.conversation_id,
            settings=self._settings,
            user_id=turn.user_id,
        )
        if tts_cancel:
            from app.services.pipecat_voice.tts_context_cancel import record_tts_context_cancel

            record_tts_context_cancel(
                self._settings,
                org_id=turn.org_id,
                user_id=turn.user_id,
                conversation_id=turn.conversation_id,
                result=tts_cancel,
            )
        if reconcile_meta is not None and self._settings is not None and turn.org_id:
            from app.services.pipecat_voice.voice_latency_metrics import (
                record_voice_barge_in_reconciliation,
            )

            record_voice_barge_in_reconciliation(
                self._settings,
                org_id=turn.org_id,
                user_id=turn.user_id,
                conversation_id=turn.conversation_id,
                reconcile_meta=reconcile_meta,
                playback_offset_ms=playback_offset_ms,
            )
        return bool(armed)

    async def _post_interrupt(
        self,
        turn: _InterruptedTurn,
        *,
        reconcile_meta: dict[str, Any] | None,
        playback_offset_ms: float | None,
        reconciled_text: str | None,
    ) -> None:
        tts_cancel: dict[str, Any] | None = None
        if self._tts_service is not None:
            from app.services.pipecat_voice.tts_context_cancel import (
                cancel_elevenlabs_tts_context,
            )

            try:
                tts_cancel = await cancel_elevenlabs_tts_context(
                    self._tts_service,
                    keep_session=True,
                ) or None
            except Exception as exc:  # noqa: BLE001
                logger.warning("pipecat_tts_context_cancel_failed error=%s", str(exc))
        try:
            armed = await asyncio.to_thread(
                self._run_post_interrupt_writes_sync,
                turn,
                tts_cancel=tts_cancel,
                reconcile_meta=reconcile_meta,
                playback_offset_ms=playback_offset_ms,
            )
            if armed and turn.org_id and turn.conversation_id:
                self._armed_stop = (str(turn.org_id), str(turn.conversation_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("pipecat_post_interrupt_writes_failed error=%s", str(exc))
        if reconciled_text is not None:
            await self._persist_interrupted_assistant_text(reconciled_text, turn)

    def _schedule_post_interrupt(self, turn: _InterruptedTurn, **kwargs: Any) -> None:
        """Run barge-in bookkeeping after the stop frame is already moving."""
        task = self.create_task(self._post_interrupt(turn, **kwargs))
        self._post_interrupt_tasks.add(task)

        def _consume(done: asyncio.Task[Any]) -> None:
            self._post_interrupt_tasks.discard(done)
            try:
                done.result()
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # noqa: BLE001
                logger.warning("pipecat_interrupted_detached_persist_failed error=%s", str(exc))
        task.add_done_callback(_consume)

    async def settle_barge_in(self) -> None:
        """Called at the start of the next confirmed user turn.

        Waits for the previous interruption's bookkeeping, then releases the
        conversation stop marker this socket armed for that interrupted turn.
        Without the release the marker (120 s TTL) would make the next voice
        turn in the same conversation return without answering.
        """
        pending = [task for task in self._post_interrupt_tasks if not task.done()]
        if pending:
            await asyncio.gather(*(asyncio.shield(task) for task in pending), return_exceptions=True)
        armed = self._armed_stop
        self._armed_stop = None
        if armed is None:
            return
        from app.services.chat_turn_cancel_service import clear_stop

        try:
            await asyncio.to_thread(clear_stop, armed[0], armed[1], settings=self._settings)
        except Exception as exc:  # noqa: BLE001
            logger.warning("pipecat_barge_in_stop_release_failed error=%s", str(exc))

    async def release_stop_marker(self) -> None:
        """Socket open/close: drop any stop marker left for this conversation.

        A marker armed by a previous socket (reconnect, or Talk closed and
        reopened inside the 120 s TTL) has no reporter left to release it, and
        every voice turn would then return without answering.
        """
        await self.settle_barge_in()
        if not self._org_id or not self._conversation_id:
            return
        from app.services.chat_turn_cancel_service import clear_stop

        try:
            await asyncio.to_thread(
                clear_stop, str(self._org_id), str(self._conversation_id), settings=self._settings
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("pipecat_stop_marker_release_failed error=%s", str(exc))

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            if not self._generating:
                # The reply is fully generated and has finished playing.
                self._draft_llm = ""
                self._draft_client = ""
                self._spoken_aligned = ""
        if isinstance(frame, InterruptionFrame) and not self.assistant_turn_live:
            # The user started a turn while nothing was being said or generated:
            # not a barge-in. Let the frame reset the pipeline, but do not cancel
            # TTS, tell the client speech was interrupted, or arm a stop marker.
            await super().process_frame(frame, direction)
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, InterruptionFrame):
            from app.services.pipecat_voice.voice_audio_origin import (
                SPEAKING,
                get_session_origin,
                get_turn_state,
                should_drop_barge_in_broadcast,
                should_suppress_interrupt,
            )

            origin = str(
                getattr(frame, "gravitre_audio_origin", None)
                or get_session_origin(self._voice_session)
            )
            turn_state = str(
                getattr(frame, "gravitre_turn_state", None)
                or get_turn_state(self._voice_session)
                or SPEAKING
            )
            warming = bool(getattr(self._voice_session, "tts_warming", False))
            if should_drop_barge_in_broadcast(
                origin=origin,
                turn_state=turn_state,
                bot_speaking=True,
                tts_warming=warming,
                settings=self._settings,
            ) or should_suppress_interrupt(
                origin=origin,
                turn_state=turn_state,
                settings=self._settings,
            ):
                logger.info(
                    "pipecat_interrupt_suppressed origin=%s turn_state=%s warming=%s",
                    origin,
                    turn_state,
                    warming,
                )
                return
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMFullResponseStartFrame):
            self._generating = True
            if self._voice_session is not None:
                self._voice_session.assistant_generating = True
            self._draft_llm = ""
            self._draft_client = ""
            self._spoken_aligned = ""
            self._last_playback_offset_ms = None
            if self._spoken_ledger is not None:
                self._spoken_ledger.reset()
            if self._voice_session is not None:
                from app.services.pipecat_voice.voice_audio_origin import SPEAKING

                self._voice_session.set_turn_state(SPEAKING)
        elif isinstance(frame, LLMTextFrame):
            self._draft_llm += str(getattr(frame, "text", None) or "")
        elif isinstance(frame, OutputTransportMessageUrgentFrame):
            msg = frame.message if isinstance(frame.message, dict) else {}
            if str(msg.get("type") or "") == "assistant_text":
                self._draft_client += str(msg.get("delta") or "")
        elif isinstance(frame, TTSTextFrame):
            self._spoken_aligned += str(getattr(frame, "text", None) or "")
        elif isinstance(frame, LLMFullResponseEndFrame):
            self._generating = False
            if self._voice_session is not None:
                self._voice_session.assistant_generating = False
        elif isinstance(frame, InterruptionFrame):
            self._generating = False
            if self._voice_session is not None:
                self._voice_session.assistant_generating = False
            offset = getattr(frame, "gravitre_playback_offset_ms", None)
            if offset is not None:
                try:
                    self._last_playback_offset_ms = float(offset)
                except (TypeError, ValueError):
                    self._last_playback_offset_ms = None
            # Spoken-text signal, in order of fidelity:
            #   1. the downstream tap's ledger (real playback-ordered TTS text),
            #   2. TTSTextFrames seen directly (only possible if this processor is
            #      ever moved downstream of tts),
            #   3. the draft — which means "assume all of it was heard", i.e. no
            #      truncation. That is the safe degradation, never an empty string.
            # An empty ledger only counts as genuine silence once the tap has
            # proven it receives frames (`ever_recorded`); otherwise a routing
            # regression would truncate every turn to nothing.
            ledger_spoken: str | None = None
            if self._spoken_ledger is not None and self._spoken_ledger.ever_recorded:
                ledger_spoken = self._spoken_ledger.snapshot()
            # Prefer the client-delta rendering: it is byte-for-byte what the
            # browser displayed and stores as history, so truncating against it
            # keeps backend and frontend agreeing on what was heard.
            draft = (self._draft_client or self._draft_llm or "").strip()
            spoken = (
                ledger_spoken
                if ledger_spoken is not None
                else (self._spoken_aligned or draft or "")
            ).strip()
            full = (draft or self._spoken_aligned or spoken).strip()
            coordinator = self._speculative_coordinator
            if coordinator is not None and hasattr(coordinator, "cancel"):
                try:
                    coordinator.cancel()
                except Exception:  # noqa: BLE001
                    pass
            payload = {
                "type": "speech.interrupted",
                "tts_provider": "elevenlabs",
                "speak_v2": False,
                "speak_v2_note": "N/A — live TTS is ElevenLabs, not Deepgram Speak v2",
                "spoken_text": spoken[:2000],
                "full_draft_text": full[:2000],
                "interrupted": True,
                "playback_offset_ms": self._last_playback_offset_ms,
                # Cancelled after the stop is in flight (see _post_interrupt):
                # awaiting the provider here held the interruption back.
                "tts_context_cancel": None,
            }
            # Phase 5 (conversational polish): tell the client which text was
            # actually heard so the next turn's history is not padded with a tail
            # the user never received. Flag-gated; off means legacy payload only.
            reconcile_meta: dict[str, Any] = {}
            reconcile_audit: dict[str, Any] | None = None
            if self._reconcile_enabled:
                from app.services.pipecat_voice.voice_conversational_polish import (
                    reconcile_played_audio,
                )

                reconciliation = reconcile_played_audio(
                    spoken_text=spoken,
                    full_draft_text=full,
                )
                reconcile_meta = reconciliation.as_meta()
                # Which signal produced `spoken` — the difference between a real
                # reconciliation and a safe degradation is otherwise invisible.
                reconcile_meta["spoken_source"] = (
                    "tap_ledger"
                    if ledger_spoken is not None
                    else ("tts_text_frames" if self._spoken_aligned else "draft_fallback")
                )
                reconcile_meta["draft_source"] = (
                    "client_deltas" if self._draft_client else "llm_frames"
                )
                payload["reconciled_text"] = reconciliation.reconciled_text[:2000]
                payload["reconcile_played_audio"] = True
                payload.update(reconcile_meta)
                reconcile_audit = dict(reconcile_meta)
            logger.info(
                "pipecat_speech_interrupted spoken_chars=%s draft_chars=%s offset_ms=%s reconcile=%s",
                len(spoken),
                len(full),
                self._last_playback_offset_ms,
                reconcile_meta or "off",
            )
            await self.push_frame(
                OutputTransportMessageUrgentFrame(message=payload),
                direction,
            )
            # Stop buffered output before any database/network reconciliation.
            await self.push_frame(frame, direction)
            # Everything below is bookkeeping, run off the event loop after the
            # stop is in flight: the conversation stop marker, the audit rows,
            # and (P0 parity) the durable rewrite to what the user actually
            # heard. The turn identity is captured now, before a new turn can
            # replace it.
            self._schedule_post_interrupt(
                self._snapshot_turn(),
                reconcile_meta=reconcile_audit,
                playback_offset_ms=self._last_playback_offset_ms,
                reconciled_text=(
                    str(payload.get("reconciled_text") or "") if self._reconcile_enabled else None
                ),
            )
            # Clear so a follow-up turn starts clean.
            self._draft_llm = ""
            self._draft_client = ""
            self._spoken_aligned = ""
            self._last_playback_offset_ms = None
            if self._spoken_ledger is not None:
                self._spoken_ledger.reset()

        if not isinstance(frame, InterruptionFrame):
            await self.push_frame(frame, direction)
