"""GravitreCognitiveLLMService — Pipecat LLM bridge to CognitiveTurnKernel.

Never uses Pipecat's default OpenAI LLM. All reasoning goes through
`execute_task_streaming(..., spoken_mode=True)` so write governance, memory,
Knowledge Fabric depth tiering, Module C honesty, and spoken register stay intact.
"""
from __future__ import annotations

import asyncio
import contextlib
import re
import time
from typing import Any

from pipecat.frames.frames import (
    AggregatedTextFrame,
    ErrorFrame,
    Frame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    OutputTransportMessageUrgentFrame,
    TTSUpdateSettingsFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.llm_service import LLMService
from pipecat.utils.text.base_text_aggregator import AggregationType

from app.core.logging import get_logger
from app.services.conversation_tier import should_acknowledge_turn
from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services.pipecat_voice.llm_context_utils import messages_from_context as _messages_from_context
from app.services.pipecat_voice.speculative_generation import SpeculativeGenerationCoordinator
from app.services.pipecat_voice.spoken_stream_filter import SpokenMarkdownStreamFilter
from app.services.pipecat_voice.utterance_gate import is_filler_only
from app.services.pipecat_voice.voice_delivery_tags import strip_and_validate_delivery_tags
from app.services.pipecat_voice.voice_latency_metrics import record_voice_llm_stage_sample
from app.services.pipecat_voice.voice_latency_tuning import (
    resolve_voice_speculative_tuning,
    resolve_voice_tts_chunk_tuning,
)
from app.services.pipecat_voice.voice_silence_guard import (
    ACK_DUE,
    SILENCE_TICK,
    SlowToolNotices,
    deep_ack_seconds,
    pick_deep_acknowledgement,
    slow_tool_notice_seconds,
    with_ack_deadline,
    with_silence_ticks,
)
from app.services.pipecat_voice.voice_tool_narration import (
    narrate_tool_completed,
    narrate_tool_started,
    narrate_tool_still_running,
    skip_spoken_tool_progress,
)
from app.services.voice_session_service import (
    normalize_spoken_text,
    reconstitute_spoken_identity_fields,
    split_speakable_chunks,
)
from app.services.chat_turn_cancel_service import is_stop_requested

logger = get_logger(__name__)

# How often a streaming voice turn re-checks the conversation stop marker.
STOP_POLL_INTERVAL_S = 0.25

# Appended to the voice turn's base prompt. Business context, memory and
# history ride along on every turn; this keeps them background.
# A cached voice system prompt is rebuilt after this long (text rebuilds per turn).
BASE_PROMPT_MAX_AGE_S = 300.0
# The speculative run and its confirmed turn both ask for the durable tail.
DURABLE_REFRESH_MIN_INTERVAL_S = 0.5

VOICE_NO_VOLUNTEERED_DATA_NOTE = (
    "Treat business context, memory and earlier conversation as background: never volunteer "
    "figures from them or run connector tools unless the user's current message asks for that "
    "or accepts your offer."
)


def merge_unanswered_turn(
    carried: str, user_text: str, history: list[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    """Fold a request cancelled before any answer into the next utterance.

    The cancelled utterance is still the last user message in the context;
    it is removed from history and joined to the new text, so "Email Sarah the
    deck" + "and cc Mike" is answered as one request. Backing off ("never
    mind", "stop") withdraws it, and an exact repeat is not doubled.
    """
    from app.services.conversation_tier import _DECLINE_CONTINUATION_RE

    carried = (carried or "").strip()
    text = (user_text or "").strip()
    if not carried or not text or _DECLINE_CONTINUATION_RE.match(text):
        return user_text, history

    def _norm(value: str) -> str:
        return " ".join(re.sub(r"[^\w\s]", " ", value.casefold()).split())

    trimmed = list(history or [])
    for idx in range(len(trimmed) - 1, -1, -1):
        row = trimmed[idx]
        if str(row.get("role") or "") == "assistant":
            break
        if str(row.get("role") or "") == "user" and _norm(str(row.get("content") or "")) == _norm(carried):
            trimmed.pop(idx)
            break
    if _norm(carried) == _norm(text) or _norm(text).startswith(_norm(carried)):
        return text, trimmed
    joiner = " " if carried[-1] in ".!?," else ", "
    return f"{carried}{joiner}{text}", trimmed


async def adopt_or_fresh(adopted: Any, fresh: Any):
    """Drain an adopted speculative run; if it was cancelled empty, run fresh.

    A speculative run that hit a stop marker (or any other early cancel) ends
    with an empty ``cancelled`` completion and no text. Adopting that verbatim
    meant the user's turn got no answer at all, so the confirmed turn falls
    back to the same fresh call it would have made without speculation.
    """
    produced_text = False
    async for event in adopted:
        if isinstance(event, AssistantStreamComplete):
            if (
                not produced_text
                and str(getattr(event, "model", "") or "") == "cancelled"
                and not str(getattr(event, "full_content", "") or "").strip()
            ):
                logger.info("pipecat_voice_speculative_cancelled_fallback_fresh")
                async for fresh_event in fresh():
                    yield fresh_event
                return
            yield event
            continue
        if isinstance(event, AssistantStreamEvent) and event.sse_type == "text-delta":
            produced_text = True
        yield event


class GravitreCognitiveLLMService(LLMService):
    """Pipecat LLMService that delegates to Gravitre One Brain."""

    def __init__(
        self,
        *,
        app_settings: Any,
        org_id: str,
        user_id: str,
        agent: dict[str, Any] | None = None,
        conversation_id: str | None = None,
        speculative_coordinator: SpeculativeGenerationCoordinator | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        # Never assign to self._settings — AIService owns that for Pipecat ServiceSettings.
        self._app_settings = app_settings
        self._org_id = org_id
        self._user_id = user_id
        self._agent = agent
        self._conversation_id = conversation_id
        # Voice-SLO follow-up (2026-09-05): shared with SpeculativePrefetchProcessor
        # via pipeline.py so a speculative run started on probable-EOT can be
        # adopted here at confirmed end-of-turn instead of re-running the call.
        self._speculative_coordinator = speculative_coordinator
        # P0 conversation parity: hydrate durable history once per voice socket.
        # Pipecat still owns the live in-socket context; this seed bridges prior
        # text/voice turns and reconnects without duplicating turns completed
        # during the current socket.
        self._durable_history_loaded = False
        self._durable_history: list[dict[str, Any]] = []
        self._durable_summary: str | None = None
        self._durable_load_lock = asyncio.Lock()
        self._interrupt_reporter: Any | None = None
        # One brain, one prompt: the canonical assistant system prompt text chat
        # builds (persona, org context, agent memory). Text rebuilds it every
        # turn; voice reuses it only while it is fresh and, for an agent whose
        # memory section is retrieved from the question, only for the same text
        # (so a speculative run and its confirmed turn share one build).
        self._base_prompt: str | None = None
        self._base_prompt_built_at = 0.0
        self._base_prompt_query: str | None = None
        self._base_prompt_lock = asyncio.Lock()
        # Rows persisted to this conversation after the seed was read (text typed
        # while Talk is open, and this socket's own voice turns), refreshed per
        # turn so voice sees what was typed and text sees what was said.
        self._durable_live_rows: list[dict[str, Any]] = []
        self._durable_watermark: str | None = None
        self._durable_owned = False
        self._durable_refreshed_at = 0.0
        self._conversation_prepared: str | None = None
        # Per-turn latency record (voice_turn_trace.VoiceTurnTrace), set by pipeline.py.
        self._turn_trace: Any | None = None
        self._turn_brain_marks: list[dict[str, Any]] = []
        # Set once this turn pushed answer text through the TTS sentence
        # aggregator, which may still be holding its last sentence.
        self._tts_text_pending = False
        # Whether anything was spoken in the current turn, and the last early
        # acknowledgement (so consecutive deep turns do not repeat it).
        self._turn_spoke = False
        self._last_ack: str | None = None
        # The request a barge-in cancelled before any answer was spoken. It is
        # merged into the next turn instead of being silently lost.
        self._carry_user_text: str | None = None
        # The current turn already merged a request carried from a cancelled one.
        self._turn_was_carried = False
        self._active_user_text = ""
        self._answer_started = False
        # ElevenLabs stability currently applied; the pipeline starts on the
        # medium baseline. Changed only when a turn's tier needs a different one.
        self._voice_stability: float | None = None

    async def _apply_tier_voice(self, tier: str | None) -> None:
        """Livelier delivery for light turns, steadier for deep (stability only).

        Sent only when the tier's value differs from what is applied, so
        consecutive same-tier turns never touch the TTS. The frame reaches the
        TTS before this turn's first sentence, so the new context opens with it.
        """
        if not bool(getattr(self._app_settings, "voice_tier_expression", True)):
            return
        try:
            from app.services.tier1_voice_service import (
                CONVERSATIONAL_VOICE_SETTINGS,
                voice_stability_for_tier,
            )

            current = (
                self._voice_stability
                if self._voice_stability is not None
                else float(CONVERSATIONAL_VOICE_SETTINGS["stability"])
            )
            target = voice_stability_for_tier(tier)
            if target == current:
                return
            from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

            await self.push_frame(
                TTSUpdateSettingsFrame(delta=ElevenLabsTTSService.Settings(stability=target))
            )
            self._voice_stability = target
        except Exception:  # noqa: BLE001 - delivery tuning must never break a turn
            logger.debug("pipecat_voice_tier_voice_skipped", exc_info=True)

    async def _ensure_durable_context(self) -> None:
        """Load the durable seed once per socket, off the event loop.

        Both the speculative run and the confirmed turn can ask first; the lock
        makes the second caller wait for the first load instead of repeating it.
        """
        if self._durable_history_loaded:
            return
        async with self._durable_load_lock:
            if self._durable_history_loaded:
                return
            history, self._durable_summary = await asyncio.to_thread(
                self._load_durable_conversation_context
            )
            self._durable_history = self._drop_trailing_unanswered_user_turns(history)
            self._durable_history_loaded = True

    async def shared_turn_inputs(self, user_text: str) -> dict[str, Any]:
        """Turn inputs text chat passes to the brain: system prompt plus injection hardening.

        Used by both the confirmed turn and the speculative run so an adopted
        speculative answer was produced under exactly the same prompt.
        """
        from app.services.shared_turn_preparation import build_turn_system_prompt, harden_against_injection

        agent_id = str((self._agent or {}).get("id") or "") or None
        if self._base_prompt_stale(user_text, agent_id=agent_id):
            async with self._base_prompt_lock:
                if self._base_prompt_stale(user_text, agent_id=agent_id):
                    try:
                        self._base_prompt = await asyncio.to_thread(
                            build_turn_system_prompt,
                            self._app_settings,
                            self._org_id,
                            user_id=self._user_id,
                            agent_id=agent_id,
                            query=user_text,
                        )
                    except Exception as exc:  # noqa: BLE001 - never make Talk unavailable
                        logger.warning("pipecat_base_prompt_build_failed org_id=%s err=%s", self._org_id, exc)
                        self._base_prompt = self._base_prompt or ""
                    self._base_prompt_built_at = time.monotonic()
                    self._base_prompt_query = user_text
        prompt = self._base_prompt or None
        if prompt:
            prompt = f"{prompt}\n\n{VOICE_NO_VOLUNTEERED_DATA_NOTE}"
            prompt = await harden_against_injection(
                self._app_settings,
                org_id=self._org_id,
                conversation_id=self._conversation_id,
                system_prompt=prompt,
                user_text=user_text,
                surface="voice",
            )
        return {"assistant_base_prompt": prompt}

    def _base_prompt_stale(self, user_text: str, *, agent_id: str | None) -> bool:
        if self._base_prompt is None:
            return True
        if time.monotonic() - self._base_prompt_built_at > BASE_PROMPT_MAX_AGE_S:
            # Connected apps and org context change; text rebuilds every turn.
            return True
        # An agent's memory section is retrieved for the question asked.
        return bool(agent_id) and self._base_prompt_query != user_text

    async def speculative_durable_context(self) -> tuple[list[dict[str, Any]], str | None, str | None]:
        """Return the same durable history/summary used by confirmed voice turns."""
        await self._ensure_durable_context()
        await self._refresh_durable_tail()
        return self._durable_rows(), self._durable_summary, self._conversation_id

    def _durable_rows(self) -> list[dict[str, Any]]:
        """Seed plus rows persisted since; merged with the socket by merge_durable_and_socket_history."""
        return [dict(m) for m in self._durable_history] + [
            {**dict(m), "_live": True} for m in self._durable_live_rows
        ]

    async def _refresh_durable_tail(self) -> None:
        """Read rows persisted to the conversation since the last read (one small query)."""
        if not self._conversation_id or not self._durable_owned:
            return
        now = time.monotonic()
        if now - self._durable_refreshed_at < DURABLE_REFRESH_MIN_INTERVAL_S:
            return
        self._durable_refreshed_at = now
        try:
            rows = await asyncio.to_thread(self._load_rows_since, self._conversation_id, self._durable_watermark)
        except Exception as exc:  # noqa: BLE001 - history refresh is best-effort
            logger.debug("pipecat_durable_refresh_failed error=%s", exc)
            return
        for row in rows:
            created = str(row.get("created_at") or "")
            if created:
                self._durable_watermark = created
            role = str(row.get("role") or "")
            content = str(row.get("content") or "")
            if role in {"user", "assistant"} and content.strip():
                self._durable_live_rows.append({"role": role, "content": content})
        self._durable_live_rows = self._durable_live_rows[-96:]

    def _load_rows_since(self, conversation_id: str, watermark: str | None) -> list[dict[str, Any]]:
        from app.workflows.repository import get_supabase_client

        query = (
            get_supabase_client(self._app_settings)
            .table("conversation_messages")
            .select("role,content,created_at")
            .eq("conversation_id", conversation_id)
        )
        if watermark:
            query = query.gt("created_at", watermark)
        response = query.order("created_at", desc=False).limit(48).execute()
        return list(getattr(response, "data", None) or [])

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMContextFrame) and getattr(frame, "speculation", False):
            # Pipecat's provisional context for a turn that has not ended. This
            # service runs its own speculative path (speculative_prefetch.py);
            # answering this frame would run the full governed turn, tools
            # included, on text the user has not finished saying.
            logger.info("pipecat_voice_provisional_context_ignored org_id=%s", self._org_id)
            return
        if isinstance(frame, LLMContextFrame):
            await self.push_frame(LLMFullResponseStartFrame())
            self._tts_text_pending = False
            try:
                await self.start_processing_metrics()
                self._turn_brain_marks = []
                await self._run_gravitre_turn(frame.context)
            except asyncio.CancelledError:
                # Barge-in cancelled this turn. If none of the answer was spoken
                # yet, keep the request for the next turn ("Email Sarah the
                # deck" ... "and cc Mike").
                # Only when nothing at all was said: once Gravitre has started
                # talking (even "let me check"), repeating the request would
                # restart the answer from the top. A request that was itself
                # carried is never carried again, so it cannot loop.
                if (
                    self._active_user_text
                    and not self._answer_started
                    and not self._turn_spoke
                    and not self._turn_was_carried
                ):
                    self._carry_user_text = self._active_user_text
                    logger.info("pipecat_voice_unanswered_turn_carried org_id=%s", self._org_id)
                raise
            except Exception as exc:  # noqa: BLE001
                # str(exc) stays in the log, which is where a stack-shaped string
                # belongs. What went downstream before was the same raw exception
                # text -- on the voice path, so the failure mode was the user
                # hearing a Python error read aloud. Local import mirrors the
                # house style below and keeps the Composer out of the module's
                # import cycle.
                from app.services.response_composer import TTS_SAFE_ERROR, safe_voice_text

                logger.exception("pipecat_cognitive_llm_failed error=%s", exc)
                # Through the content gate even though the input is already the
                # safe line. The AST guard only checks that this argument is a
                # reference, so if it ever becomes a variable carrying something
                # else, this is what still stands between that and the listener.
                spoken = safe_voice_text(TTS_SAFE_ERROR)
                await self.push_error(error_msg=spoken, exception=exc)
                await self.push_frame(ErrorFrame(error=spoken))
            finally:
                await self.stop_processing_metrics()
                await self.push_frame(LLMFullResponseEndFrame())
                self._finish_turn_trace()
            return
        await self.push_frame(frame, direction)

    async def _run_gravitre_turn(self, context: Any) -> None:
        from app.operators.agent_intelligence import get_agent_intelligence
        from app.services.composer_failure_triggers import (
            VOICE_TURN_FAILURE_MESSAGE,
            is_voice_turn_failure_probe,
        )
        from app.services.operator_task_intent import resolve_voice_turn_routing

        # Disposable fault path, isolated smoke org + sentinel conversation only.
        # The except-handler in process_frame is unreachable otherwise, so without
        # this the fix above could only ever be argued from code review.
        if is_voice_turn_failure_probe(
            org_id=self._org_id, conversation_id=self._conversation_id
        ):
            raise RuntimeError(VOICE_TURN_FAILURE_MESSAGE)

        user_text, history = _messages_from_context(context)
        if not user_text:
            return
        if is_filler_only(user_text):
            # Backstop for UtteranceGateProcessor: a hesitation is not a request.
            logger.info("pipecat_voice_filler_turn_skipped org_id=%s", self._org_id)
            return
        trace = self._turn_trace
        if trace is not None:
            trace.begin_turn()
        self._turn_spoke = False
        if self._interrupt_reporter is not None:
            # A confirmed new user turn ends the interrupted one: let its
            # bookkeeping finish and release the stop marker it armed, so this
            # turn is not mistaken for a stopped one.
            await self._interrupt_reporter.settle_barge_in()
            if self._interrupt_reporter.conversation_id:
                self._conversation_id = self._interrupt_reporter.conversation_id
        await self._ensure_durable_context()
        # Same conversation row and ledger ingest text runs before the brain,
        # so the first turn's approvals persist (minted ids get their row now).
        await self._prepare_conversation(user_text)
        await self._refresh_durable_tail()
        if trace is not None:
            trace.note("durable_ready")
        history = self._merge_durable_and_socket_history(self._durable_rows(), history)
        user_text = reconstitute_spoken_identity_fields(user_text)
        carried, self._carry_user_text = self._carry_user_text, None
        session = self._voice_session()
        if session is not None and session.is_echo_of_bot(user_text, strict=True):
            # The mic picked up Gravitre's own voice. Answering it would
            # restart the reply from the beginning.
            logger.info("pipecat_voice_echo_turn_skipped org_id=%s", self._org_id)
            return
        self._turn_was_carried = bool(carried)
        if carried:
            user_text, history = merge_unanswered_turn(carried, user_text, history)
        self._active_user_text = user_text
        self._answer_started = False
        if self._interrupt_reporter is not None:
            self._interrupt_reporter.begin_turn(user_text)
        if await asyncio.to_thread(
            is_stop_requested,
            str(self._org_id or ""),
            self._conversation_id,
            settings=self._app_settings,
        ):
            logger.info(
                "pipecat_voice_chat_stop org_id=%s conversation_id=%s",
                self._org_id,
                self._conversation_id,
            )
            return
        intelligence = get_agent_intelligence()
        turn_inputs = await self.shared_turn_inputs(user_text)
        if trace is not None:
            trace.note("prompt_ready")
        # Same helper and inputs (final text + merged history) as the
        # speculative run, so an adopted run was produced under the same tier.
        voice_tier, voice_mode = resolve_voice_turn_routing(user_text, history=history)
        if trace is not None:
            # Fallback only: the brain's own routing.conversationTier wins.
            trace.set_turn_meta(tier=voice_tier.tier)
        logger.info(
            "pipecat_voice_conversation_tier org_id=%s tier=%s reason=%s mode=%s",
            self._org_id,
            voice_tier.tier,
            voice_tier.reason,
            voice_mode,
        )
        await self._apply_tier_voice(voice_tier.tier)
        # Same guardrails text chat runs before streaming (kill switch, rate
        # limit, budget, moderation, model policy). Moderation is a network
        # round trip, so it runs concurrently with the brain's preparation and
        # nothing is spoken or shown until it passes; a refusal is spoken.
        from app.services.shared_turn_preparation import TurnGuardrailBlocked, guard_spoken_turn

        guard_task: asyncio.Task[None] | None = asyncio.create_task(
            guard_spoken_turn(
                self._app_settings,
                org_id=self._org_id,
                user_text=user_text,
                system_prompt=str(turn_inputs.get("assistant_base_prompt") or ""),
                history=history,
                mode=voice_mode,
            )
        )
        # A barge-in can cancel this turn before the guard is awaited; retrieve
        # its result anyway so a refusal never surfaces as an unhandled task error.
        guard_task.add_done_callback(lambda t: t.cancelled() or t.exception())
        if trace is not None:
            guard_task.add_done_callback(lambda _t: trace.note("guard_done"))

        async def _guard_refused() -> bool:
            nonlocal guard_task
            if guard_task is None:
                return False
            task, guard_task = guard_task, None
            try:
                await task
            except TurnGuardrailBlocked as blocked:
                logger.info("pipecat_voice_guardrail_blocked org_id=%s kind=%s", self._org_id, blocked.kind)
                await self._speak_narration(blocked.spoken)
                return True
            return False
        # `normalize_spoken_text` forces sentence-terminal punctuation onto
        # whatever text it is given. Raw LLM deltas arrive as small,
        # sentence-unaware fragments ("I need", " the", " recipient,"), so
        # normalizing each delta independently punctuated *every fragment*
        # ("I.need.the.recipient.,...") — corrupting both the displayed chat
        # text and the TTS input (each fragment was then spoken as its own
        # isolated "sentence", producing the choppy, robotic pacing).
        #
        # Fix: send raw deltas to the client for progressive text display
        # (matches the HTTP-duplex path), and only feed TTS complete,
        # sentence-chunked text via `split_speakable_chunks` + normalize —
        # exactly the pattern `stream_voice_turn_events` already uses.
        text_buffer = ""
        turn_start = time.perf_counter()
        # Phase 2 (conversational-realism): progressive narration during
        # multi-step tool execution. Tracks toolCallId -> toolName from
        # tool-input-available so the matching tool-output-available (which
        # carries no toolName of its own) can still be narrated honestly.
        # Dedupe tool-started narration per tool name so a turn calling the
        # same tool twice doesn't repeat "Let me check X" — real state, said
        # once, not a chatty loop.
        tool_names_by_call_id: dict[str, str] = {}
        narrated_tool_starts: set[str] = set()
        # Round-count audit (2026-09-06): Addendum 3 found consequential_write_
        # shaped turns spend 3.2-3.7s per round in "tool-execution latency
        # between LLM calls" but could only attribute that to "some round", not
        # a specific tool — pipecat_voice_turn_latency only logs at LLM-call
        # boundaries (data-intelligence events), never at tool-call boundaries.
        # This closes that gap: real wall-clock elapsed between this specific
        # tool's tool-input-available and tool-output-available, logged per
        # call so the next probe can name the slow tool instead of the round.
        tool_call_started_at: dict[str, float] = {}
        first_delta_at: float | None = None
        first_speakable_chunk_at: float | None = None
        tts_requested_at: float | None = None
        complete_event: AssistantStreamComplete | None = None
        # Phase 6 (conversational-realism): real TTFB metrics for the LLM
        # bridge itself. GravitreCognitiveLLMService never streams tokens
        # through Pipecat's stock LLM adapters, so this stage's TTFB is not
        # measured automatically anywhere else — start/stop it explicitly so
        # GravitreVoiceLatencyObserver (pipeline.py) actually receives a real
        # sample for this processor instead of silence.
        await self.start_ttfb_metrics()
        # Client-facing deltas were pushed raw, so markdown the model emitted
        # reached the browser verbatim (measured 2026-09-08). TTS was already
        # protected because it receives whole sentences; this protects the
        # transcript the user reads.
        client_text_filter = SpokenMarkdownStreamFilter()
        spec_tuning = resolve_voice_speculative_tuning(self._app_settings)
        chunk_tuning = resolve_voice_tts_chunk_tuning(self._app_settings)
        prefix_extra = (
            spec_tuning.prefix_max_extra_words if spec_tuning.prefix_adopt else 0
        )
        # Voice-SLO follow-up (2026-09-05): if a speculative run was started on
        # Deepgram Flux's probable-EOT signal (speculative_prefetch.py) and its
        # text matches this now-confirmed user_text exactly, adopt its
        # buffered/live output instead of calling execute_task_streaming()
        # again — any tokens it already produced before confirmation land
        # here instantly, which is the entire latency win this closes. A
        # mismatch (or no coordinator/run at all) falls back to the exact
        # same fresh call as before — zero regression risk on the default
        # path.
        speculative_run = (
            self._speculative_coordinator.adopt(
                user_text,
                prefix_max_extra_words=prefix_extra,
                tier=voice_tier.tier,
            )
            if self._speculative_coordinator
            else None
        )
        speculative_outcome = "adopted" if speculative_run is not None else "fresh"
        # The brain writes its pre-LLM checkpoints here (execute_task_streaming
        # latency_marks); an adopted speculative run brought its own.
        fresh_brain_marks: dict[str, Any] = {}
        self._turn_brain_marks = [fresh_brain_marks]
        if speculative_run is not None:
            self._turn_brain_marks.append(getattr(speculative_run, "latency_marks", None) or {})
        if trace is not None:
            trace.set_turn_meta(speculative_outcome=speculative_outcome)
        if speculative_run is not None:
            logger.info(
                "pipecat_voice_speculative_generation_adopted org_id=%s chars=%s prefix_adopt=%s",
                self._org_id,
                len(user_text),
                prefix_extra > 0,
            )

        def _fresh_stream():
            return intelligence.execute_task_streaming(
                settings=self._app_settings,
                org_id=self._org_id,
                user_id=self._user_id,
                query=user_text,
                agent_id=str((self._agent or {}).get("id") or "") or None,
                conversation_history=history or None,
                history_summary=self._durable_summary,
                conversation_id=self._conversation_id,
                spoken_mode=True,
                mode=voice_mode,
                latency_marks=fresh_brain_marks,
                **turn_inputs,
            )

        if speculative_run is not None:
            events_source = adopt_or_fresh(speculative_run.events(), _fresh_stream)
        else:
            events_source = _fresh_stream()
        # Dead-air guard: while one slow tool call keeps the stream silent, say
        # (honestly) that it is still running instead of leaving the line quiet.
        notice_interval_s = slow_tool_notice_seconds(self._app_settings)
        slow_tool_notices = SlowToolNotices(notice_interval_s)
        events_source = with_silence_ticks(events_source, interval_s=notice_interval_s)
        # Medium and deep turns run the pipeline before their first token: if
        # nothing has been said shortly after the turn is confirmed, acknowledge
        # it. Light turns and backing off ("never mind") are answered at once.
        if should_acknowledge_turn(voice_tier):
            events_source = with_ack_deadline(events_source, delay_s=deep_ack_seconds(self._app_settings))
        last_stop_poll = time.perf_counter()
        async for event in events_source:
            if guard_task is not None and await _guard_refused():
                aclose = getattr(events_source, "aclose", None)
                if aclose is not None:
                    with contextlib.suppress(Exception):
                        await aclose()
                await self.stop_ttfb_metrics()
                return
            # A Redis GET per stream event, run on the event loop, stalled the
            # audio pacing of every live session. Check off-loop, at most every
            # STOP_POLL_INTERVAL_S (barge-in also cancels this task directly).
            now = time.perf_counter()
            poll_stop = now - last_stop_poll >= STOP_POLL_INTERVAL_S
            if poll_stop:
                last_stop_poll = now
            if poll_stop and await asyncio.to_thread(
                is_stop_requested,
                str(self._org_id or ""),
                self._conversation_id,
                settings=self._app_settings,
            ):
                logger.info(
                    "pipecat_voice_chat_stop_mid_stream org_id=%s conversation_id=%s",
                    self._org_id,
                    self._conversation_id,
                )
                break
            if event is ACK_DUE:
                # The guard was settled at the top of this loop, so a refused
                # turn never gets here. Only when nothing was said yet.
                if first_delta_at is None and not self._turn_spoke:
                    ack = pick_deep_acknowledgement(self._last_ack)
                    self._last_ack = ack
                    logger.info("pipecat_voice_deep_ack org_id=%s", self._org_id)
                    await self._speak_narration(ack)
                continue
            if event is SILENCE_TICK:
                due = slow_tool_notices.due(
                    tool_call_started_at,
                    tool_names_by_call_id,
                    now=time.perf_counter(),
                    skip=skip_spoken_tool_progress,
                )
                if due is not None:
                    tool_name, is_repeat = due
                    logger.info(
                        "pipecat_voice_slow_tool_notice org_id=%s tool=%s repeat=%s",
                        self._org_id,
                        tool_name,
                        is_repeat,
                    )
                    await self._flush_client_text(client_text_filter)
                    await self._speak_narration(narrate_tool_still_running(tool_name, repeat=is_repeat))
                continue
            if isinstance(event, AssistantStreamComplete):
                complete_event = event
                continue
            if not isinstance(event, AssistantStreamEvent):
                continue
            if event.sse_type == "data-intelligence":
                # Voice latency instrumentation (2026-09-04): the Pipecat bridge
                # previously discarded this event entirely, so the routing/
                # reasoning latency breakdown that unified-turn already
                # computes was never visible for voice turns. Log-only —
                # never sent to the client, zero behavior change.
                payload = event.payload if isinstance(event.payload, dict) else {}
                data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
                if isinstance(data, dict) and trace is not None:
                    trace.attach_intelligence(data)
                if isinstance(data, dict):
                    routing = data.get("routing") if isinstance(data.get("routing"), dict) else {}
                    logger.info(
                        "pipecat_voice_turn_latency org_id=%s pre_llm_ms=%s conversation_tier=%s "
                        "reasoning_depth=%s routing_tier=%s effective_mode=%s model_ttft_ms=%s "
                        "pre_model_ms=%s wall_to_first_token_ms=%s cached_prompt_tokens=%s "
                        "cognitive_stage_ms=%s",
                        self._org_id,
                        int((time.perf_counter() - turn_start) * 1000),
                        routing.get("conversationTier") or voice_tier.tier,
                        routing.get("reasoningDepth"),
                        data.get("routingTier"),
                        data.get("effectiveMode"),
                        routing.get("modelTtftMs"),
                        routing.get("preModelMs"),
                        routing.get("wallToFirstTokenMs"),
                        routing.get("cachedPromptTokens"),
                        routing.get("cognitiveStageMs"),
                    )
                continue
            if event.sse_type == "tool-input-available":
                payload = event.payload if isinstance(event.payload, dict) else {}
                call_id = str(payload.get("toolCallId") or "")
                tool_name = str(payload.get("toolName") or "")
                if call_id and tool_name:
                    tool_names_by_call_id[call_id] = tool_name
                    tool_call_started_at[call_id] = time.perf_counter()
                if tool_name and tool_name not in narrated_tool_starts:
                    narrated_tool_starts.add(tool_name)
                    if not skip_spoken_tool_progress(tool_name):
                        await self._flush_client_text(client_text_filter)
                        await self._speak_narration(narrate_tool_started(tool_name))
                continue
            if event.sse_type == "tool-output-available":
                payload = event.payload if isinstance(event.payload, dict) else {}
                call_id = str(payload.get("toolCallId") or "")
                tool_name = tool_names_by_call_id.get(call_id, "")
                started_at = tool_call_started_at.pop(call_id, None)
                if tool_name and started_at is not None:
                    logger.info(
                        "pipecat_voice_tool_latency org_id=%s tool=%s elapsed_ms=%s since_turn_start_ms=%s",
                        self._org_id,
                        tool_name,
                        int((time.perf_counter() - started_at) * 1000),
                        int((time.perf_counter() - turn_start) * 1000),
                    )
                narration = narrate_tool_completed(tool_name, payload.get("output"))
                if narration and not skip_spoken_tool_progress(tool_name):
                    await self._flush_client_text(client_text_filter)
                    await self._speak_narration(narration)
                continue
            if event.sse_type != "text-delta":
                continue
            if first_delta_at is None:
                first_delta_at = time.perf_counter()
                if trace is not None:
                    trace.note("first_token", first_delta_at)
                await self.stop_ttfb_metrics()
                logger.info(
                    "pipecat_voice_turn_latency org_id=%s first_text_delta_ms=%s",
                    self._org_id,
                    int((first_delta_at - turn_start) * 1000),
                )
            payload = event.payload if isinstance(event.payload, dict) else {}
            delta = str(payload.get("delta") or payload.get("textDelta") or "")
            if not delta:
                continue
            client_delta = client_text_filter.feed(delta)
            if client_delta:
                await self.push_frame(
                    OutputTransportMessageUrgentFrame(
                        message={"type": "assistant_text", "delta": client_delta}
                    )
                )
            text_buffer += delta
            chunks, text_buffer = split_speakable_chunks(
                text_buffer,
                min_chars=chunk_tuning.min_chars,
                aggressive=chunk_tuning.v2_enabled,
            )
            for chunk in chunks:
                spoken = self._sanitize_for_tts(chunk)
                if spoken:
                    self._answer_started = True
                    if first_speakable_chunk_at is None:
                        first_speakable_chunk_at = time.perf_counter()
                        if trace is not None:
                            trace.note("first_speakable", first_speakable_chunk_at)
                    await self._push_spoken_text(spoken)
                    if tts_requested_at is None:
                        tts_requested_at = time.perf_counter()
        # A stream that produced no events (or was stopped) still settles the guard.
        if guard_task is not None and await _guard_refused():
            await self.stop_ttfb_metrics()
            return
        # A construct the model never closed (e.g. a stray "*") is still held in
        # the filter; emit it so the transcript is not truncated.
        await self._flush_client_text(client_text_filter)
        # Flush any trailing clause that never hit a sentence boundary (e.g.
        # a short answer with no terminal punctuation) so the tail of the
        # reply is not silently dropped from speech.
        tail = self._sanitize_for_tts(text_buffer)
        if tail:
            self._answer_started = True
            if first_speakable_chunk_at is None:
                first_speakable_chunk_at = time.perf_counter()
                if trace is not None:
                    trace.note("first_speakable", first_speakable_chunk_at)
            await self._push_spoken_text(tail)
            if tts_requested_at is None:
                tts_requested_at = time.perf_counter()

        def _ms(at: float | None) -> int | None:
            return int((at - turn_start) * 1000) if at is not None else None

        # Audit inserts block; the reply is still being spoken, so they run in
        # a worker thread instead of pausing its audio.
        await asyncio.to_thread(
            record_voice_llm_stage_sample,
            self._app_settings,
            org_id=self._org_id,
            user_id=self._user_id,
            conversation_id=self._conversation_id,
            llm_first_token_ms=_ms(first_delta_at),
            llm_first_speakable_chunk_ms=_ms(first_speakable_chunk_at),
            tts_requested_ms=_ms(tts_requested_at),
            speculative_outcome=speculative_outcome,
            speculative_v2=spec_tuning.v2_enabled,
            tts_chunk_v2=chunk_tuning.v2_enabled,
        )
        if complete_event is not None and trace is not None:
            trace.set_turn_meta(turn_id=str(getattr(complete_event, "message_id", None) or "") or None)
        if complete_event is not None:
            durable_assistant_text = str(getattr(complete_event, "full_content", None) or "").strip()
            if durable_assistant_text:
                preassigned_assistant_id = str(getattr(complete_event, "message_id", None) or "") or None
                if self._interrupt_reporter is not None:
                    self._interrupt_reporter.mark_turn_persisted(
                        conversation_id=self._conversation_id,
                        assistant_message_id=preassigned_assistant_id,
                    )
                persisted_id, assistant_id = await asyncio.to_thread(
                    self._persist_completed_voice_turn,
                    user_text=user_text,
                    assistant_text=durable_assistant_text,
                    complete_event=complete_event,
                )
                if persisted_id:
                    self._conversation_id = persisted_id
                    from app.services.shared_turn_preparation import persist_turn_summary

                    await asyncio.to_thread(
                        persist_turn_summary,
                        self._app_settings,
                        conversation_id=persisted_id,
                        org_id=self._org_id,
                        user_id=self._user_id,
                        complete=complete_event,
                    )
                    if self._interrupt_reporter is not None:
                        self._interrupt_reporter.mark_turn_persisted(
                            conversation_id=persisted_id,
                            assistant_message_id=assistant_id,
                        )
            # The websocket stays open across many spoken turns. The browser therefore
            # cannot use socket close as a turn boundary. Emit an explicit completion
            # marker after the final assistant text has been flushed so the live UI can
            # commit this turn immediately without requiring the Talk orb to unmount.
            await self.push_frame(
                OutputTransportMessageUrgentFrame(
                    message={
                        "type": "assistant_turn.complete",
                        "turn_id": str(getattr(complete_event, "message_id", None) or ""),
                        "conversation_id": self._conversation_id,
                        # Client text deltas remain the primary transcript because they
                        # include real narration; full_content is only a fallback when
                        # no delta survived to the browser.
                        "text": str(getattr(complete_event, "full_content", None) or ""),
                    }
                )
            )

            from app.services.pipecat_voice.voice_latency_metrics import record_voice_slo_metric
            from app.services.voice_slo import METRIC_B_ID, operator_task_for_metric_b

            completion_ms = int((time.perf_counter() - turn_start) * 1000)
            if operator_task_for_metric_b(
                loop_stage_spoken=bool(complete_event.pending_task),
                tool_results=complete_event.tool_results,
            ):
                await asyncio.to_thread(
                    record_voice_slo_metric,
                    self._app_settings,
                    metric=METRIC_B_ID,
                    org_id=self._org_id,
                    user_id=self._user_id,
                    conversation_id=self._conversation_id,
                    ms=completion_ms,
                    source="pipecat_composed_final",
                    operator_task=True,
                    composed=True,
                )

    def _load_durable_conversation_context(self) -> tuple[list[dict[str, Any]], str | None]:
        """Load the owned durable conversation before the first voice turn.

        This is intentionally read-only and best-effort. A missing/invalid
        conversation must never make Talk unavailable.
        """
        if not self._conversation_id:
            return [], None
        try:
            from app.services.conversation_context_service import load_conversation_summary
            from app.workflows.repository import get_supabase_client

            client = get_supabase_client(self._app_settings)
            owned = (
                client.table("conversations")
                .select("id,last_summary")
                .eq("id", self._conversation_id)
                .eq("org_id", self._org_id)
                .eq("user_id", self._user_id)
                .limit(1)
                .execute()
            )
            if not getattr(owned, "data", None):
                return [], None
            summary = load_conversation_summary(
                client,
                conversation_id=self._conversation_id,
                org_id=self._org_id,
                user_id=self._user_id,
            )
            response = (
                client.table("conversation_messages")
                .select("role,content,created_at")
                .eq("conversation_id", self._conversation_id)
                .order("created_at", desc=True)
                .limit(48)
                .execute()
            )
            rows = list(getattr(response, "data", None) or [])
            rows.reverse()
            self._durable_owned = True
            if rows:
                self._durable_watermark = str(rows[-1].get("created_at") or "") or None
            history = [
                {"role": str(row.get("role") or ""), "content": str(row.get("content") or "")}
                for row in rows
                if str(row.get("role") or "") in {"user", "assistant"}
                and str(row.get("content") or "").strip()
            ]
            return history, summary
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "pipecat_durable_history_load_failed org_id=%s conversation_id=%s error=%s",
                self._org_id,
                self._conversation_id,
                str(exc),
            )
            return [], None

    @staticmethod
    def _drop_trailing_unanswered_user_turns(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Strip user messages at the end of the pre-socket seed that never got a reply.

        The seed is background. A question typed before Talk opened whose
        answer never landed (a failed or abandoned text turn) is not a pending
        request: left at the tail it sits right before the first thing the user
        says in voice, and the brain answered it instead -- CRM numbers spoken
        on open, or a connector call nobody asked for in this session.
        """
        trimmed = [dict(message) for message in history or []]
        dropped = 0
        while trimmed and str(trimmed[-1].get("role") or "") == "user":
            trimmed.pop()
            dropped += 1
        if dropped:
            logger.info("pipecat_durable_unanswered_user_turns_dropped count=%s", dropped)
        return trimmed

    @staticmethod
    def _merge_durable_and_socket_history(
        durable: list[dict[str, Any]], socket_history: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Durable history (seed + rows persisted since), then unpersisted socket turns."""
        from app.services.pipecat_voice.llm_context_utils import merge_durable_and_socket_history

        return merge_durable_and_socket_history(durable, socket_history)

    async def _prepare_conversation(self, user_text: str) -> None:
        if not self._conversation_id or not self._user_id:
            return
        from app.services.shared_turn_preparation import prepare_turn_conversation

        ensure_row = self._conversation_prepared != self._conversation_id
        try:
            prepared = await prepare_turn_conversation(
                self._app_settings,
                org_id=self._org_id,
                user_id=self._user_id,
                conversation_id=self._conversation_id,
                user_text=user_text,
                ensure_row=ensure_row,
            )
        except Exception as exc:  # noqa: BLE001 - never make Talk unavailable
            logger.warning("pipecat_conversation_prepare_failed error=%s", exc)
            return
        if prepared:
            if ensure_row and prepared == self._conversation_id:
                self._durable_owned = True
            self._conversation_id = prepared
            self._conversation_prepared = prepared

    def _persist_completed_voice_turn(
        self,
        *,
        user_text: str,
        assistant_text: str,
        complete_event: AssistantStreamComplete,
    ) -> tuple[str | None, str | None]:
        """Persist a completed voice turn through the same durable store as text."""
        if not assistant_text.strip():
            return None, None
        try:
            from app.services.shared_turn_preparation import persist_completed_turn

            persisted_id, assistant_id = persist_completed_turn(
                self._app_settings,
                org_id=self._org_id,
                user_id=self._user_id,
                conversation_id=self._conversation_id,
                user_text=user_text,
                assistant_text=assistant_text,
                complete=complete_event,
            )
            return persisted_id, assistant_id
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "pipecat_voice_turn_persist_failed org_id=%s conversation_id=%s error=%s",
                self._org_id,
                self._conversation_id,
                str(exc),
            )
            return None, None

    async def _flush_client_text(self, filt: SpokenMarkdownStreamFilter) -> None:
        """Release withheld transcript text before another writer emits.

        Narration pushes its own ``assistant_text`` frame, so anything the filter
        is still holding must go out first or the transcript would show the two
        out of order.
        """
        pending = filt.flush()
        if pending:
            await self.push_frame(
                OutputTransportMessageUrgentFrame(
                    message={"type": "assistant_text", "delta": pending}
                )
            )

    async def _speak_narration(self, text: str) -> None:
        """Phase 2 (conversational-realism): speak one real milestone sentence.

        Goes through the same security gate + normalization as every other
        piece of spoken output (``_sanitize_for_tts``), and through the same
        text-delta transport frame so the live transcript shows exactly what
        was said — narration is not a side channel, it is real turn content.
        """
        if not text:
            return
        await self.push_frame(
            OutputTransportMessageUrgentFrame(
                message={"type": "assistant_text", "delta": text + " "}
            )
        )
        spoken = self._sanitize_for_tts(text)
        if spoken:
            self._turn_spoke = True
            self._note_bot_speech(spoken)
            await self._push_narration_speech(spoken)

    async def _push_narration_speech(self, spoken: str) -> None:
        """Speak a narration sentence now, not when the next text arrives.

        The TTS service's sentence aggregator only releases a sentence once it
        sees the first character of the next one, so a milestone pushed while
        the brain works was held until the answer's first token and spoken with
        it. A narration is a complete sentence: hand it to the TTS as one,
        unless answer text is already waiting in the aggregator (then the old
        path keeps the order). The LLMTextFrame still goes downstream for the
        interrupt reporter's draft, marked not for TTS and not for the context
        (the TTS's own spoken-text frames carry it there, as before).
        """
        if self._tts_text_pending:
            await self._push_spoken_text(spoken)
            return
        if self._turn_trace is not None:
            self._turn_trace.note("tts_requested")
        draft = LLMTextFrame(spoken + " ")
        draft.skip_tts = True
        draft.append_to_context = False
        await self.push_frame(draft)
        # Trailing space as for every other pushed segment (see _push_spoken_text).
        await self.push_frame(AggregatedTextFrame(spoken + " ", AggregationType.SENTENCE))

    async def _push_spoken_text(self, spoken: str) -> None:
        """Push one already-sanitized, already-stripped clause of spoken text.

        Regression fix (2026-09-06, live user report: "voice reverted to
        sounding robotic"): `_sanitize_for_tts` (via `strip_and_validate_delivery_tags`,
        which unconditionally `.strip()`s) always returns text with NO leading
        or trailing whitespace. Every call site here (narration sentences,
        main-answer speakable chunks, the trailing-clause flush) calls
        `_push_llm_text` independently, each producing its own `LLMTextFrame`.
        Pipecat's `SimpleTextAggregator` (the TTS service's own text
        aggregator) concatenates the raw characters of every incoming
        `TextFrame` into one running buffer with **no separator inserted
        between frames** — confirmed live via Railway logs: a
        `consequential_write_shaped` turn's actual ElevenLabs "Generating TTS"
        payload read
        "...knowledge base.Found 3.I can't send that email from the
        information provided.I don't have Sarah's email address..." — every
        sentence/narration boundary glued to the next with zero whitespace.
        This reads as garbled/run-on text to ElevenLabs Flash v2.5, producing
        exactly the "robotic"/unnatural cadence reported live, on any turn
        that narrates a tool call (this bug does not reach `simple_conversational`
        turns with no tool narration, which is why some voice turns still
        sounded fine while others did not).

        Fix: append exactly one trailing space to every independently-pushed
        spoken segment, so two adjacent frames are never glued together at a
        sentence/clause boundary. `strip_and_validate_delivery_tags` already
        collapses any 2+ run of whitespace to one within a single chunk, so
        this can never produce a double space; the next chunk's own leading
        strip means no chunk ever contributes a space of its own.
        """
        if self._turn_trace is not None:
            self._turn_trace.note("tts_requested")
        self._tts_text_pending = True
        self._turn_spoke = True
        self._note_bot_speech(spoken)
        await self._push_llm_text(spoken + " ")

    def _voice_session(self) -> Any:
        return getattr(self._interrupt_reporter, "_voice_session", None)

    def _note_bot_speech(self, spoken: str) -> None:
        session = self._voice_session()
        if session is not None:
            session.note_bot_speech(spoken)

    def _finish_turn_trace(self) -> None:
        """Hand the turn's brain checkpoints to the trace and close the turn."""
        trace = self._turn_trace
        if trace is None:
            return
        try:
            marks = next((m for m in self._turn_brain_marks if m), None)
            if marks:
                trace.attach_brain_marks(marks)
            trace.end_turn()
        except Exception as exc:  # noqa: BLE001 - latency evidence must never break a turn
            logger.debug("pipecat_voice_turn_trace_finish_failed error=%s", exc)

    def _sanitize_for_tts(self, chunk: str) -> str:
        """Security gate + spoken-format normalization before text reaches TTS.

        Conversational-realism Phase 5: any ``[[delivery:...]]``-shaped
        content (or anything else tag-shaped) in model-generated text is
        untrusted by default per the Agent Security Gateway's "knowledge is
        data, system policy is authority" principle, and must never reach
        TTS unvalidated. Runs BEFORE ``normalize_spoken_text`` so a stripped
        tag never leaves stray punctuation/spacing behind.
        """
        scan = strip_and_validate_delivery_tags(chunk)
        if scan.had_injection_attempt:
            logger.warning(
                "pipecat_voice_delivery_tag_injection_blocked org_id=%s rejected=%r",
                self._org_id,
                scan.rejected_raw_tags[:5],
            )
        from app.services.pipecat_voice.spoken_pronunciations import apply_spoken_aliases

        return apply_spoken_aliases(
            normalize_spoken_text(scan.clean_text),
            str(getattr(self._app_settings, "voice_spoken_aliases", "") or ""),
        )
