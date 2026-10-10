"""Track assistant text and report precise barge-in for ElevenLabs TTS.

Deepgram Speak v2 sendInterrupt/SpeakV2SpeechInterrupted applies only when TTS
is Deepgram Speak. Gravitre live TTS is ElevenLabs Flash over WebSocket, so we
emulate the useful contract: on InterruptionFrame, emit spoken_so_far vs
full_draft plus optional client playback_offset_ms.
"""
from __future__ import annotations

import asyncio
import time
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
from app.services.pipecat_voice.voice_reply_playback import (
    ANSWER,
    NOTHING_HEARD_MARKER,
    TRUNCATION_MARKER,
    ReplyPlayback,
    disconnect_heard_offset,
    normalize_segment_kind,
)

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


@dataclass(frozen=True)
class _HeardContext:
    """What is known at the barge-in about the reply that was cut.

    ``server_offset`` is where the server-side estimate (TTS words that left
    the output transport) puts the end of the heard text, as an offset into
    ``reply.draft``; ``server_text`` is that estimate as text, filler included.
    """

    reply: ReplyPlayback | None
    reply_id: int | None
    server_offset: int | None
    server_text: str
    still_generating: bool


def resolve_heard_answer(
    ctx: _HeardContext,
    *,
    offset: int | None = None,
    grounded: bool = False,
) -> tuple[str, dict[str, Any]]:
    """The assistant text to store for a cut reply, and how it was derived.

    Only answer text is stored: an acknowledgement ("Sure, let me look.") or
    tool narration ("Let me check your CRM.") was said, but it is not the
    answer, and a stored message that starts with it reads to the model as an
    answer that never got going. With ``grounded`` the text is cut at
    ``offset`` (the browser's played position when it reported one) and marked
    when the user did not hear all of it.
    """
    reply = ctx.reply
    meta: dict[str, Any] = {}
    use_offset = offset if offset is not None else ctx.server_offset
    if reply is None or not reply.segments or use_offset is None:
        # No labelled draft to map onto: the estimate as it was.
        text = ctx.server_text
        meta["heard_text_basis"] = "server_text"
        answer_full = text
    elif offset is None and not reply.has_non_answer():
        # Answer-only reply cut by the server estimate: exactly the reconciled text.
        text = ctx.server_text
        meta["heard_text_basis"] = "server_text"
        answer_full = reply.answer_text_upto(None)
    else:
        text = reply.answer_text_upto(use_offset)
        answer_full = reply.answer_text_upto(None)
        meta["heard_text_basis"] = "answer_segments"
        meta["non_answer_chars_dropped"] = sum(
            min(seg.end, use_offset) - seg.start
            for seg in reply.segments
            if seg.kind != ANSWER and seg.start < use_offset
        )
    truncated = ctx.still_generating or len(text.strip()) < len((answer_full or "").strip())
    meta["answer_truncated"] = bool(truncated)
    if grounded and truncated:
        text = f"{text.strip()} {TRUNCATION_MARKER}" if text.strip() else NOTHING_HEARD_MARKER
        meta["truncation_marked"] = True
    return text, meta


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
        playback_tracker: Any | None = None,
        playback_grounded_history_enabled: bool = False,
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
        # The last real barge-in, until the next confirmed turn consumes it.
        self._last_barge_in: dict[str, Any] | None = None
        # Labelled draft of the live reply (filler / progress / answer
        # segments), shared with the socket's playback tracker when there is one.
        self._playback_tracker = playback_tracker
        self._playback_grounded = bool(playback_grounded_history_enabled)
        self._reply: ReplyPlayback | None = None
        # Called with (assistant_message_id, stored_text) after a barge-in
        # rewrote a stored assistant row, so cached copies can follow.
        self.on_assistant_rewritten: Any | None = None
        # voice_playback_grounded_history_v1: heard text of a reply the socket
        # dropped before the turn was stored, applied once it is.
        self._pending_disconnect_cut: str | None = None
        if voice_session is not None:
            voice_session.answer_expected = self.answer_expected
            voice_session.speech_stop_handler = self.silence_current_reply

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

    def _current_reply_id(self) -> int | None:
        reply_id = getattr(self._voice_session, "reply_id", None)
        return reply_id if isinstance(reply_id, int) else None

    def _note_assistant_text(self, delta: str, kind: Any) -> None:
        if not delta:
            return
        kind = normalize_segment_kind(kind)
        if self._reply is None:
            reply = None
            if self._playback_tracker is not None:
                try:
                    reply = self._playback_tracker.reply(self._current_reply_id())
                except Exception:  # noqa: BLE001
                    reply = None
            self._reply = reply if reply is not None else ReplyPlayback(reply_id=self._current_reply_id())
            if self._reply.draft:
                # This processor is the only writer of a reply's text; text
                # already there belongs to a turn that never finished. Start clean
                # so the draft and the segments cannot drift.
                self._reply.draft = ""
                self._reply.segments = []
        if self._playback_tracker is not None and self._reply.reply_id is not None:
            self._playback_tracker.note_assistant_text(delta, kind, self._reply.reply_id)
        else:
            self._reply.add_text(delta, kind)

    def begin_turn(self, user_text: str) -> None:
        self._active_user_text = str(user_text or "").strip()
        self._active_assistant_message_id = None

    def mark_turn_persisted(self, *, conversation_id: str | None, assistant_message_id: str | None) -> None:
        if conversation_id:
            self._conversation_id = conversation_id
        self._active_assistant_message_id = assistant_message_id or None
        pending, self._pending_disconnect_cut = self._pending_disconnect_cut, None
        if pending is not None and assistant_message_id:
            # The socket dropped while this reply was still generating; its
            # completed row was just written in full. Cut it to what was heard.
            task = self.create_task(self._persist_interrupted_assistant_text(pending))
            self._post_interrupt_tasks.add(task)
            task.add_done_callback(self._post_interrupt_tasks.discard)

    async def reconcile_on_disconnect(self) -> dict[str, Any] | None:
        """voice_playback_grounded_history_v1: store only what was heard of a dropped reply.

        The socket went away mid-reply (network drop, tab closed): the browser
        cannot report any more, and the full reply is (or is about to be)
        stored. Cut it to the answer text heard, from the last periodic
        playback report or the server estimate, and mark it as cut, so after a
        reconnect the model sees only what the user heard. A reply that was
        heard in full is left alone. Returns what was decided (for logs/tests).
        """
        if not self._playback_grounded or self._playback_tracker is None:
            return None
        tracker = self._playback_tracker
        reply_id = tracker.audio_reply_id()
        reply = tracker.reply(reply_id, create=False) if reply_id is not None else None
        if reply is None or not reply.segments:
            return None
        offset, meta = disconnect_heard_offset(reply)
        # Only the newest reply can still be generating; an older reply whose
        # audio was the last to play is complete.
        still_generating = bool(self._generating) and reply_id == tracker.current_reply_id()
        heard = _HeardContext(
            reply=reply,
            reply_id=reply_id,
            server_offset=offset,
            server_text=reply.answer_text_upto(offset),
            still_generating=still_generating,
        )
        text, resolved = resolve_heard_answer(heard, offset=offset, grounded=True)
        meta.update(resolved)
        meta["reply_id"] = reply_id
        if not resolved.get("answer_truncated"):
            meta["action"] = "heard_in_full"
            return meta
        turn = self._snapshot_turn()
        if not turn.assistant_message_id:
            # Not stored yet (still generating): cut it when it is.
            self._pending_disconnect_cut = text
            meta["action"] = "pending_until_persisted"
        else:
            await self._persist_interrupted_assistant_text(text, turn)
            meta["action"] = "rewritten"
        logger.info(
            "pipecat_disconnect_heard_resolved reply_id=%s source=%s action=%s chars=%s",
            reply_id,
            meta.get("heard_source"),
            meta.get("action"),
            len(text),
        )
        return meta

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
        callback = self.on_assistant_rewritten
        if callback is not None and turn.assistant_message_id:
            # The completed row may already be cached (with the full reply) by
            # the bridge's live history; give it the stored text.
            try:
                callback(str(turn.assistant_message_id), reconciled_text.strip())
            except Exception:  # noqa: BLE001
                logger.debug("pipecat_assistant_rewrite_callback_failed", exc_info=True)
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
        """Blocking barge-in audit rows. Runs in a worker thread, never on the loop.

        The stop marker is not armed here: it is armed in-process before the
        interruption leaves this processor and shared through Redis by
        :meth:`_arm_shared_stop_sync`, which does not wait for the TTS cancel.
        """
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
        return True

    def _arm_stop_now(self, turn: _InterruptedTurn) -> bool:
        """Block uncommitted writes for this conversation before anything is awaited.

        In-process and I/O free, so it runs on the loop the moment the
        barge-in is recognized: a write commit check in this process sees it
        even while the TTS cancel or the Redis write are still in flight.
        """
        if not turn.org_id or not turn.conversation_id:
            return False
        from app.services.chat_turn_cancel_service import arm_local_stop

        armed = arm_local_stop(str(turn.org_id), str(turn.conversation_id))
        if armed:
            self._armed_stop = (str(turn.org_id), str(turn.conversation_id))
        return armed

    def _arm_shared_stop_sync(self, turn: _InterruptedTurn) -> bool:
        """Share the stop with other workers (Redis) and audit it. Worker thread."""
        from app.services.voice_barge_in_write import mark_voice_barge_in_stop

        return bool(
            mark_voice_barge_in_stop(
                org_id=turn.org_id,
                conversation_id=turn.conversation_id,
                settings=self._settings,
                user_id=turn.user_id,
            )
        )

    def _tts_context_ids(self) -> list[str]:
        """Audio contexts the TTS currently holds (synchronous getters only)."""
        tts = self._tts_service
        if tts is None:
            return []
        ids: list[str] = []
        try:
            getter = getattr(tts, "get_audio_contexts", None)
            if callable(getter):
                ids.extend(str(c) for c in (getter() or []) if c)
            for attr in ("get_active_audio_context_id",):
                active = getattr(tts, attr, None)
                if callable(active) and active():
                    ids.append(str(active()))
            turn_id = getattr(tts, "_turn_context_id", None)
            if isinstance(turn_id, str) and turn_id:
                ids.append(turn_id)
        except Exception:  # noqa: BLE001 - identity binding is best effort
            pass
        return list(dict.fromkeys(ids))

    async def _cancel_tts_context(self) -> dict[str, Any] | None:
        if self._tts_service is None:
            return None
        from app.services.pipecat_voice.tts_context_cancel import (
            cancel_elevenlabs_tts_context,
        )

        try:
            return await cancel_elevenlabs_tts_context(
                self._tts_service,
                keep_session=True,
            ) or None
        except Exception as exc:  # noqa: BLE001
            logger.warning("pipecat_tts_context_cancel_failed error=%s", str(exc))
            return None

    async def _resolve_durable_text(
        self, heard: _HeardContext
    ) -> tuple[str, dict[str, Any]]:
        """Answer text to store; with the grounded flag, cut at the browser's played position."""
        if not self._playback_grounded:
            return resolve_heard_answer(heard)
        reply = heard.reply
        tracker = self._playback_tracker
        reported = None
        if tracker is not None and heard.reply_id is not None:
            try:
                reported = await tracker.wait_for_client_report(heard.reply_id)
            except Exception:  # noqa: BLE001
                reported = None
        meta: dict[str, Any] = {"heard_source": "server_estimate"}
        offset: int | None = None
        if reported is not None and reply is not None and reported.client_played_ms is not None:
            offset, method = reply.char_offset_for_played_ms(reported.client_played_ms)
            if heard.server_offset is not None:
                # Audio cannot be played before it was sent: the server estimate
                # is an upper bound on what the browser can have played.
                offset = min(offset, heard.server_offset)
            meta.update(
                {
                    "heard_source": "client_playback",
                    "played_to_text": method,
                    "client_played_ms": int(round(reported.client_played_ms)),
                    "sent_audio_ms": int(round(reply.sent_audio_ms)),
                }
            )
        text, resolved = resolve_heard_answer(heard, offset=offset, grounded=True)
        meta.update(resolved)
        logger.info(
            "pipecat_interrupted_heard_resolved reply_id=%s source=%s played_ms=%s chars=%s",
            heard.reply_id,
            meta.get("heard_source"),
            meta.get("client_played_ms"),
            len(text),
        )
        return text, meta

    async def _post_interrupt(
        self,
        turn: _InterruptedTurn,
        *,
        reconcile_meta: dict[str, Any] | None,
        playback_offset_ms: float | None,
        reconciled_text: str | None,
        heard: _HeardContext | None = None,
    ) -> None:
        # The in-process stop is already armed (_arm_stop_now). The shared one
        # and the TTS cancel are independent: neither waits for the other.
        shared_stop = asyncio.ensure_future(asyncio.to_thread(self._arm_shared_stop_sync, turn))
        tts_cancel = await self._cancel_tts_context()
        try:
            await shared_stop
        except Exception as exc:  # noqa: BLE001
            logger.warning("pipecat_barge_in_shared_stop_failed error=%s", str(exc))
        try:
            await asyncio.to_thread(
                self._run_post_interrupt_writes_sync,
                turn,
                tts_cancel=tts_cancel,
                reconcile_meta=reconcile_meta,
                playback_offset_ms=playback_offset_ms,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("pipecat_post_interrupt_writes_failed error=%s", str(exc))
        if reconciled_text is not None:
            durable_text = reconciled_text
            if heard is not None:
                try:
                    durable_text, heard_meta = await self._resolve_durable_text(heard)
                    if heard_meta.get("heard_source") == "client_playback" and self._settings is not None:
                        await asyncio.to_thread(self._record_grounded_reconciliation, turn, heard_meta)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("pipecat_interrupted_heard_resolve_failed error=%s", str(exc))
                    durable_text = reconciled_text
            await self._persist_interrupted_assistant_text(durable_text, turn)

    def _record_grounded_reconciliation(self, turn: _InterruptedTurn, meta: dict[str, Any]) -> None:
        if not turn.org_id:
            return
        from app.services.pipecat_voice.voice_latency_metrics import (
            record_voice_barge_in_reconciliation,
        )

        record_voice_barge_in_reconciliation(
            self._settings,
            org_id=turn.org_id,
            user_id=turn.user_id,
            conversation_id=turn.conversation_id,
            reconcile_meta={"stage": "playback_grounded", **meta},
            playback_offset_ms=meta.get("client_played_ms"),
        )

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

    def consume_barge_in(self) -> dict[str, Any] | None:
        """The barge-in the next confirmed turn follows, once: reply id and time.

        None when the turn did not cut anything off (the bot was idle).
        """
        info, self._last_barge_in = self._last_barge_in, None
        return info

    async def settle_barge_in(self, *, release: bool = True) -> None:
        """Called at the start of the next confirmed user turn.

        Waits for the previous interruption's bookkeeping, then releases the
        conversation stop marker this socket armed for that interrupted turn.
        Without the release the marker (120 s TTL) would make the next voice
        turn in the same conversation return without answering.

        ``release=False`` (a "cancel it" turn) keeps the marker armed so a
        write of the cancelled work that is still on its way to commit is
        refused; the next ordinary turn releases it.
        """
        pending = [task for task in self._post_interrupt_tasks if not task.done()]
        if pending:
            await asyncio.gather(*(asyncio.shield(task) for task in pending), return_exceptions=True)
        if not release:
            return
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

    async def silence_current_reply(self) -> bool:
        """Silence this reply ("stop talking") and keep the work behind it running.

        Nothing goes upstream, so the brain's turn (and any authorized tool
        call in it) is not cancelled, and no stop marker is armed, so its
        writes are not refused. Downstream, the reply's audio is cut by
        identity, the TTS and output transport are flushed, and the client is
        told speech stopped while work continues. The reply's text and its
        normal completion still go out; nothing more of it is spoken.
        Returns False when there was nothing to silence.
        """
        session = self._voice_session
        if session is None or not (self.assistant_turn_live or getattr(session, "assistant_generating", False)):
            return False
        reply_id = getattr(session, "reply_id", None)
        if not isinstance(reply_id, int):
            return False
        session.mute_reply(reply_id)
        work_continues = bool(self._generating or getattr(session, "assistant_generating", False))
        spoken = ""
        if self._spoken_ledger is not None and self._spoken_ledger.ever_recorded:
            spoken = self._spoken_ledger.snapshot()
        logger.info(
            "pipecat_speech_silenced reply_id=%s work_continues=%s spoken_chars=%s",
            reply_id,
            work_continues,
            len(spoken),
        )
        await self.push_frame(
            OutputTransportMessageUrgentFrame(
                message={
                    "type": "speech.interrupted",
                    "tts_provider": "elevenlabs",
                    "interrupted": True,
                    "intent": "speech_stop",
                    "work_continues": work_continues,
                    "reply_id": reply_id,
                    "spoken_text": spoken[:2000],
                    "full_draft_text": (self._draft_client or self._draft_llm or "").strip()[:2000],
                    "playback_offset_ms": None,
                    "tts_context_cancel": None,
                }
            ),
            FrameDirection.DOWNSTREAM,
        )
        notice_sent = getattr(session, "muted_notice_sent", None)
        if work_continues and isinstance(notice_sent, set) and reply_id not in notice_sent:
            notice_sent.add(reply_id)
            await self.push_frame(
                OutputTransportMessageUrgentFrame(
                    message={
                        "type": "assistant_notice",
                        "kind": "speech_stopped_work_continues",
                        "reply_id": reply_id,
                        "text": "Okay, I'll stop talking. I'm still working on it, and the answer will show here.",
                    }
                ),
                FrameDirection.DOWNSTREAM,
            )
        # Flush what the TTS and the output transport already hold for this
        # reply. Pushed downstream only: the brain upstream keeps running.
        flush = InterruptionFrame()
        setattr(flush, "gravitre_speech_only", True)
        await self.push_frame(flush, FrameDirection.DOWNSTREAM)
        task = self.create_task(self._cancel_tts_context())
        self._post_interrupt_tasks.add(task)
        task.add_done_callback(self._post_interrupt_tasks.discard)
        return True

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
            if self._voice_session is not None:
                # Read by the transcript relay to mark backchannel finals.
                self._voice_session.bot_speaking = True
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            if self._voice_session is not None:
                self._voice_session.bot_speaking = False
            if not self._generating:
                # The reply is fully generated and has finished playing.
                self._draft_llm = ""
                self._draft_client = ""
                self._spoken_aligned = ""
                self._reply = None
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
            # A real barge-in. Before anything is awaited (the base class's
            # interruption handling, the provider cancel, Redis): refuse
            # uncommitted writes of the interrupted work, and cut the
            # interrupted reply's audio off by identity.
            interrupted_turn = self._snapshot_turn()
            self._arm_stop_now(interrupted_turn)
            interrupted_reply_id = getattr(self._voice_session, "reply_id", None)
            cancel_audio = getattr(self._voice_session, "cancel_reply_audio", None)
            if isinstance(interrupted_reply_id, int) and callable(cancel_audio):
                # The TTS has not seen this interruption yet (it is downstream),
                # so every context it holds belongs to the reply being cut off,
                # including one whose audio was never seen downstream.
                for context_id in self._tts_context_ids():
                    self._voice_session.bind_audio_context(context_id, interrupted_reply_id)
                cancel_audio(interrupted_reply_id)
            self._last_barge_in = {
                "reply_id": interrupted_reply_id if isinstance(interrupted_reply_id, int) else None,
                "at": time.monotonic(),
            }
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMFullResponseStartFrame):
            self._generating = True
            if self._voice_session is not None:
                self._voice_session.assistant_generating = True
            self._draft_llm = ""
            self._draft_client = ""
            self._spoken_aligned = ""
            self._last_playback_offset_ms = None
            self._reply = None
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
                delta = str(msg.get("delta") or "")
                self._draft_client += delta
                self._note_assistant_text(delta, msg.get("kind"))
        elif isinstance(frame, TTSTextFrame):
            self._spoken_aligned += str(getattr(frame, "text", None) or "")
        elif isinstance(frame, LLMFullResponseEndFrame):
            self._generating = False
            if self._voice_session is not None:
                self._voice_session.assistant_generating = False
        elif isinstance(frame, InterruptionFrame):
            still_generating = self._generating
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
            reply_id = getattr(self._voice_session, "reply_id", None)
            if isinstance(reply_id, int):
                payload["reply_id"] = reply_id
            reply = self._reply
            if self._playback_tracker is not None and isinstance(reply_id, int):
                try:
                    self._playback_tracker.mark_interrupted(reply_id)
                except Exception:  # noqa: BLE001
                    pass
            # Phase 5 (conversational polish): tell the client which text was
            # actually heard so the next turn's history is not padded with a tail
            # the user never received. Flag-gated; off means legacy payload only.
            reconcile_meta: dict[str, Any] = {}
            reconcile_audit: dict[str, Any] | None = None
            heard_ctx: _HeardContext | None = None
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
                # Where the estimate puts the heard end in the labelled draft.
                # Valid only when the draft is the client text the segments index.
                server_offset: int | None = None
                if (
                    reply is not None
                    and self._draft_client
                    and reply.draft == self._draft_client
                ):
                    lead = len(self._draft_client) - len(self._draft_client.lstrip())
                    server_offset = lead + len(reconciliation.reconciled_text)
                heard_ctx = _HeardContext(
                    reply=reply,
                    reply_id=reply_id if isinstance(reply_id, int) else None,
                    server_offset=server_offset,
                    server_text=reconciliation.reconciled_text,
                    still_generating=still_generating,
                )
                answer_text, _answer_meta = resolve_heard_answer(heard_ctx)
                # The answer part of what was heard: the text history keeps.
                payload["reconciled_answer_text"] = answer_text[:2000]
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
                interrupted_turn,
                reconcile_meta=reconcile_audit,
                playback_offset_ms=self._last_playback_offset_ms,
                reconciled_text=(
                    str(payload.get("reconciled_text") or "") if self._reconcile_enabled else None
                ),
                heard=heard_ctx,
            )
            # Clear so a follow-up turn starts clean.
            self._draft_llm = ""
            self._draft_client = ""
            self._spoken_aligned = ""
            self._last_playback_offset_ms = None
            self._reply = None
            if self._spoken_ledger is not None:
                self._spoken_ledger.reset()

        if not isinstance(frame, InterruptionFrame):
            await self.push_frame(frame, direction)
