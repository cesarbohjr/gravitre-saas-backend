"""Speculative prefetch + speculative generation on interim STT.

Two distinct mechanisms, both cancel-and-restart on partial-transcript change:

  1) READ-only cache warming (original, always active on any growing interim
     partial): warm dialogue settings + sentiment, tool-retrieval query
     embedding cache, READ knowledge retrieval (never for write-shaped text),
     tool-document embedding cache. Never bypasses CognitiveTurnKernel, never
     executes tools or consequential writes.

  2) Genuine speculative LLM generation (2026-09-05 voice-SLO follow-up):
     on Deepgram Flux's ProposedUserStoppedSpeakingFrame ("probably done")
     signal, starts a real, cancelable CognitiveTurnKernel reasoning call via
     SpeculativeGenerationCoordinator — the same call GravitreCognitiveLLMService
     would eventually make at confirmed end-of-turn. Gated by the same
     write-shaped conservatism as (1): never speculatively runs the full
     turn (tool routing, memory writes, write-governance staging) for text
     that looks like a connector write — only CONVERSATION/KNOWLEDGE-shaped
     turns speculate. If the user keeps talking past the probable-EOT (a new,
     materially different interim arrives), the pending speculative run is
     cancelled — composes with, but is a separate mechanism from, barge-in
     (ElevenLabsInterruptReporter cancels BOT SPEECH; this cancels a
     background LLM call that hasn't been adopted/spoken yet).

     The run executes as a dry run (app.services.speculative_execution):
     durable writes are deferred until adoption, connector WRITEs and approval
     staging/consumption are refused, and the run is bounded by a timeout and
     a buffer cap (speculative_generation.SpeculativeBounds).
"""
from __future__ import annotations

import asyncio
from typing import Any

from pipecat.frames.frames import (
    EagerEndOfTurnCancelFrame,
    EagerTranscriptionFrame,
    Frame,
    InterimTranscriptionFrame,
    ProposedUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.core.logging import get_logger
from app.services.pipecat_voice.llm_context_utils import (
    merge_durable_and_socket_history,
    messages_from_context,
)
from app.services.pipecat_voice.utterance_gate import is_non_utterance
from app.services.pipecat_voice.speculative_generation import (
    SpeculativeGenerationCoordinator,
    SpeculativeGenerationRun,
    load_revision_versions,
    with_turn_inputs,
    start_speculative_run,
)
from app.services.pipecat_voice.voice_latency_tuning import (
    resolve_voice_speculative_bounds,
    resolve_voice_speculative_tuning,
    speculative_interim_breaks_run,
    voice_request_revisions_enabled,
)
from app.services.speculative_execution import outside_speculation

logger = get_logger(__name__)


# Quiet time an interim transcript must hold before its read-only warm-up runs.
PREFETCH_DEBOUNCE_S = 0.15


def _warm_knowledge_blocking(settings: Any, org_id: str, query: str, agent_id: str | None) -> None:
    """Worker-thread knowledge warm: its own event loop, so blocking I/O stays off the voice loop."""
    from app.services.unified_retrieval_service import UnifiedRetrievalService

    svc = UnifiedRetrievalService(settings)
    asyncio.run(svc.retrieve_knowledge_rows(org_id=org_id, query=query, top_k=4, agent_id=agent_id))


def _load_dialogue_settings_blocking(org_id: str, settings: Any, client: Any) -> Any:
    """Worker-thread wrapper: load_chat_dialogue_settings is async but never awaits."""
    from app.services.chat_dialogue_settings import load_chat_dialogue_settings

    return asyncio.run(load_chat_dialogue_settings(org_id, settings, client=client))


def _looks_write_shaped(text: str) -> bool:
    """Conservative gate — speculative path must never touch write execution."""
    try:
        from app.services.operator_task_intent import (
            looks_like_operator_task,
            should_keep_full_reasoning_for_spoken,
        )

        if looks_like_operator_task(text) or should_keep_full_reasoning_for_spoken(text):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.services.conversational_planning_engine import is_direct_connector_write_intent

        return bool(is_direct_connector_write_intent(text or ""))
    except Exception:  # noqa: BLE001
        lowered = (text or "").lower()
        return any(
            needle in lowered
            for needle in (
                "email ",
                "send ",
                "create ",
                "delete ",
                "update ",
                "book ",
                "schedule ",
                "post to",
                "publish ",
            )
        )


class SpeculativePrefetchProcessor(FrameProcessor):
    """Fire-and-forget READ-only warm path on high-confidence interim transcripts."""

    def __init__(
        self,
        *,
        app_settings: Any,
        org_id: str,
        user_id: str,
        agent: dict[str, Any] | None = None,
        min_chars: int = 8,
        conversation_id: str | None = None,
        llm_context: Any | None = None,
        speculative_coordinator: SpeculativeGenerationCoordinator | None = None,
        durable_context_provider: Any | None = None,
        turn_inputs_provider: Any | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._app_settings = app_settings
        self._org_id = org_id
        self._user_id = user_id
        self._agent = agent if isinstance(agent, dict) else {}
        spec_tuning = resolve_voice_speculative_tuning(app_settings)
        self._spec_tuning = spec_tuning
        self._min_chars = spec_tuning.min_chars if spec_tuning.v2_enabled else min_chars
        # Always-on run bounds, versioned request revisions and the strict
        # adoption check.
        self._spec_bounds = resolve_voice_speculative_bounds(app_settings)
        self._revisions_v1 = voice_request_revisions_enabled(app_settings)
        self._last_partial = ""
        self._task: asyncio.Task[None] | None = None
        # Voice-SLO follow-up (2026-09-05): genuine speculative generation —
        # shared with GravitreCognitiveLLMService via pipeline.py.
        self._conversation_id = conversation_id
        self._llm_context = llm_context
        self._speculative_coordinator = speculative_coordinator
        self._durable_context_provider = durable_context_provider
        # Same prompt inputs as the confirmed turn (GravitreCognitiveLLMService.shared_turn_inputs),
        # so adopting a speculative answer never changes which prompt produced it.
        self._turn_inputs_provider = turn_inputs_provider
        self._last_speculative_text = ""
        # Awaited before a speculative run calls the brain: releases the stop
        # marker an interrupted previous turn armed (interrupt_reporter
        # settle_barge_in). Without it the run read that marker, returned an
        # empty "cancelled" answer, was adopted, and the user heard nothing.
        self.before_run = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, InterimTranscriptionFrame):
            text = (frame.text or "").strip()
            if len(text) >= self._min_chars and text != self._last_partial:
                self._last_partial = text
                if self._task and not self._task.done():
                    self._task.cancel()
                self._task = self.create_task(self._prefetch(text))
                # The probable-EOT that started a speculative generation run
                # (if any) was based on stale text — the user kept talking
                # with materially new content. Cancel now rather than let it
                # run to adopt on stale text (adopt() would reject the
                # mismatch anyway, but cancelling here frees the compute
                # immediately instead of at confirmed-EOT).
                if self._speculative_coordinator is not None:
                    if self._revisions_v1:
                        self._speculative_coordinator.note_transcript(text)
                    if text != self._last_speculative_text and speculative_interim_breaks_run(
                        self._last_speculative_text,
                        text,
                        strict=self._revisions_v1,
                        v2_enabled=self._spec_tuning.v2_enabled,
                        max_extra_words=self._prefix_extra_words(),
                    ):
                        self._speculative_coordinator.cancel()
        elif isinstance(frame, EagerTranscriptionFrame):
            # Flux's eager end of turn: the earliest "probably done" signal,
            # 200-400 ms before the committed EndOfTurn. Its transcript is the
            # best text for the turn so far.
            text = (frame.text or "").strip()
            if text:
                self._last_partial = text
                if self._speculative_coordinator is not None and self._revisions_v1:
                    self._speculative_coordinator.note_transcript(text)
            self._maybe_start_speculative_generation()
        elif isinstance(frame, EagerEndOfTurnCancelFrame):
            # The user kept talking. Free the run now; the next eager or
            # committed end of turn starts a fresh one.
            if self._speculative_coordinator is not None:
                self._speculative_coordinator.cancel()
            self._last_speculative_text = ""
        elif isinstance(frame, ProposedUserStoppedSpeakingFrame):
            self._maybe_start_speculative_generation()
        await self.push_frame(frame, direction)

    def _prefix_extra_words(self) -> int:
        tuning = self._spec_tuning
        return tuning.prefix_max_extra_words if tuning.prefix_adopt else 0

    def _maybe_start_speculative_generation(self) -> None:
        """Start speculation without ever blocking the frame that triggered it.

        Called before the eager/proposed-stop frame is pushed on: an error here
        used to propagate out of process_frame, so the frame was never
        forwarded and the turn lost its stop signal. Speculation is optional;
        the frame is not.
        """
        try:
            self._start_speculative_generation()
        except Exception as exc:  # noqa: BLE001 - logged; the confirmed turn still runs fresh
            logger.exception("pipecat_voice_speculative_generation_start_failed error=%s", exc)

    def _start_speculative_generation(self) -> None:
        """Deepgram Flux's own 'probably done' signal — begin a real,
        cancelable reasoning call now, ahead of confirmed end-of-turn.
        """
        if self._speculative_coordinator is None:
            return
        text = self._last_partial
        if len(text) < self._min_chars or text == self._last_speculative_text:
            # Either nothing usable yet, or this exact text is already the
            # one currently speculating (a duplicate Proposed-stop signal
            # with no new interim in between) — do not restart identical work.
            return
        if is_non_utterance(text):
            # Hesitations never start a brain call, speculative or confirmed.
            return
        if _looks_write_shaped(text):
            # Same conservative gate as the read-only prefetch's knowledge
            # warm: never speculatively run the full governed turn (tool
            # routing, memory writes, write-governance staging) against
            # text that has not been confirmed by the user yet — a
            # speculative "Email Sarah" run superseded by the user actually
            # saying "Email Mike" must never leave staged approval/ledger
            # state behind. Read-only prefetch above still applies; only
            # real generation is skipped here.
            return
        from app.services.conversation_tier import is_continuation_utterance

        if is_continuation_utterance(text):
            # "yes, do that" / "go ahead" / "the second one" answer whatever is
            # pending, and pending approvals live in task_state this processor
            # cannot see. A speculative run could act on a confirmation the user
            # is still qualifying ("yes... wait"), so these wait for the
            # confirmed turn.
            return
        if bool(getattr(self._app_settings, "voice_interrupt_intents_v1", False)):
            from app.services.pipecat_voice.backchannel_classifier import (
                InterruptIntent,
                classify_interrupt_intent,
            )

            if classify_interrupt_intent(text) in (InterruptIntent.SPEECH_STOP, InterruptIntent.TASK_CANCEL):
                # voice_interrupt_intents_v1: "stop talking" and "cancel it" are
                # handled without the brain; speculating on them only burns a call.
                return
        from app.services.voice_session_service import reconstitute_spoken_identity_fields

        query = reconstitute_spoken_identity_fields(text)
        self._last_speculative_text = text
        revision = self._speculative_coordinator.note_transcript(text) if self._revisions_v1 else None
        run_holder: list[SpeculativeGenerationRun] = []
        latency_marks: dict[str, Any] = {}

        async def _runner():
            from app.operators.agent_intelligence import get_agent_intelligence
            from app.services.operator_task_intent import resolve_voice_turn_routing

            if self.before_run is not None:
                # The previous turn's barge-in bookkeeping is confirmed work,
                # not part of this speculation: never deferred or dropped.
                with outside_speculation():
                    await self.before_run()
            intelligence = get_agent_intelligence()
            _, socket_history = messages_from_context(self._llm_context) if self._llm_context else ("", [])
            history = socket_history
            history_summary = None
            conversation_id = self._conversation_id
            if self._durable_context_provider is not None:
                # Awaited, not called: the first load on a resumed conversation
                # is two Supabase queries and must not run on the event loop.
                durable, history_summary, provider_conversation_id = await self._durable_context_provider()
                history = merge_durable_and_socket_history(list(durable or []), list(socket_history or []))
                conversation_id = provider_conversation_id or conversation_id
            if self._revisions_v1 and run_holder:
                # Bind the run to the state it answers; adoption requires the
                # confirmed turn to see the same versions.
                run_holder[0].versions = await load_revision_versions(
                    self._app_settings,
                    org_id=self._org_id,
                    conversation_id=conversation_id,
                    history=history,
                    history_summary=history_summary,
                )
            turn_inputs = await self._turn_inputs_provider(query) if self._turn_inputs_provider is not None else {}
            if run_holder and run_holder[0].versions is not None:
                run_holder[0].versions = with_turn_inputs(
                    run_holder[0].versions,
                    org_id=self._org_id,
                    user_id=self._user_id,
                    agent_id=str(self._agent.get("id") or "") or None,
                    turn_inputs=turn_inputs,
                )
            # Same helper and inputs as the confirmed turn (adopt-on-match parity).
            spec_tier, spec_mode = resolve_voice_turn_routing(query, history=history or None)
            if run_holder:
                run_holder[0].tier = spec_tier.tier
            stream = intelligence.execute_task_streaming(
                settings=self._app_settings,
                org_id=self._org_id,
                user_id=self._user_id,
                query=query,
                agent_id=str(self._agent.get("id") or "") or None,
                conversation_history=history or None,
                history_summary=history_summary,
                conversation_id=conversation_id,
                spoken_mode=True,
                mode=spec_mode,
                latency_marks=latency_marks,
                **turn_inputs,
            )
            async for event in stream:
                yield event

        run = start_speculative_run(
            text=query,
            runner=_runner,
            create_task=self.create_task,
            bounds=self._spec_bounds,
            revision=revision,
        )
        run_holder.append(run)
        run.latency_marks = latency_marks
        self._speculative_coordinator.set_run(run)
        logger.info(
            "pipecat_voice_speculative_generation_started org_id=%s chars=%s",
            self._org_id,
            len(text),
        )

    async def _prefetch(self, text: str) -> None:
        try:
            # Interims arrive every ~200 ms while the user talks and each one
            # cancels the previous prefetch. Worker threads cannot be cancelled,
            # so wait briefly first: only a partial that holds still is warmed.
            await asyncio.sleep(PREFETCH_DEBOUNCE_S)
            from app.services.sentiment_friction_service import get_sentiment_friction_service
            from app.services.unified_turn_tool_retrieval import (
                is_task_shaped_for_retrieval,
                warm_tool_document_embeddings,
            )
            from app.workflows.repository import get_supabase_client

            # Runs on every interim transcript. Both calls are blocking (a
            # Supabase read and a classifier), and on the event loop they stall
            # the real-time audio pacing of every session on this worker.
            client = get_supabase_client(self._app_settings)
            await asyncio.to_thread(
                _load_dialogue_settings_blocking, self._org_id, self._app_settings, client
            )
            await asyncio.to_thread(get_sentiment_friction_service().analyze, text, None)

            use_emb, shape, query = is_task_shaped_for_retrieval(text)
            write_shaped = _looks_write_shaped(text)
            embed_warmed = False
            knowledge_warmed = False
            tool_docs_warmed = 0

            if use_emb and len((query or "").strip()) >= self._min_chars:
                from app.rag.tool_retrieval_embedding import embed_tool_retrieval_query_timed

                await asyncio.to_thread(
                    embed_tool_retrieval_query_timed,
                    query,
                    self._app_settings,
                )
                embed_warmed = True

            # Catalog vector warm — never invokes tools.
            try:
                tool_docs_warmed = int(
                    await asyncio.to_thread(
                        warm_tool_document_embeddings,
                        settings=self._app_settings,
                    )
                )
            except Exception:  # noqa: BLE001
                tool_docs_warmed = 0

            # READ knowledge warm only when not write-shaped (still no tool exec).
            if use_emb and not write_shaped and len((query or "").strip()) >= self._min_chars:
                try:
                    # The retrieval stack is async in name only: the embedding
                    # call and both Supabase reads block. Awaited on the event
                    # loop, each interim transcript froze the voice pipeline for
                    # the whole round trip (seconds when the provider retries).
                    await asyncio.to_thread(
                        _warm_knowledge_blocking,
                        self._app_settings,
                        self._org_id,
                        query,
                        str(self._agent.get("id") or "") or None,
                    )
                    knowledge_warmed = True
                except Exception as exc:  # noqa: BLE001
                    logger.debug("pipecat_speculative_knowledge_warm_failed error=%s", exc)

            logger.info(
                "pipecat_speculative_prefetch org_id=%s chars=%s shape=%s write_shaped=%s "
                "embed_warmed=%s knowledge_warmed=%s tool_docs_warmed=%s write_exec=false",
                self._org_id,
                len(text),
                shape,
                write_shaped,
                embed_warmed,
                knowledge_warmed,
                tool_docs_warmed,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.debug("pipecat_speculative_prefetch_failed error=%s", exc)
