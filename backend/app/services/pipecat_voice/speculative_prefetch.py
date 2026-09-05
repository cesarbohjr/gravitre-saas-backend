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
"""
from __future__ import annotations

import asyncio
from typing import Any

from pipecat.frames.frames import (
    Frame,
    InterimTranscriptionFrame,
    ProposedUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.core.logging import get_logger
from app.services.pipecat_voice.llm_context_utils import messages_from_context
from app.services.pipecat_voice.speculative_generation import (
    SpeculativeGenerationCoordinator,
    start_speculative_run,
)

logger = get_logger(__name__)


def _looks_write_shaped(text: str) -> bool:
    """Conservative gate — speculative path must never touch write execution."""
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
        min_chars: int = 12,
        conversation_id: str | None = None,
        llm_context: Any | None = None,
        speculative_coordinator: SpeculativeGenerationCoordinator | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._app_settings = app_settings
        self._org_id = org_id
        self._user_id = user_id
        self._agent = agent if isinstance(agent, dict) else {}
        self._min_chars = min_chars
        self._last_partial = ""
        self._task: asyncio.Task[None] | None = None
        # Voice-SLO follow-up (2026-09-05): genuine speculative generation —
        # shared with GravitreCognitiveLLMService via pipeline.py.
        self._conversation_id = conversation_id
        self._llm_context = llm_context
        self._speculative_coordinator = speculative_coordinator
        self._last_speculative_text = ""

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
                if self._speculative_coordinator is not None and text != self._last_speculative_text:
                    self._speculative_coordinator.cancel()
        elif isinstance(frame, ProposedUserStoppedSpeakingFrame):
            self._maybe_start_speculative_generation()
        await self.push_frame(frame, direction)

    def _maybe_start_speculative_generation(self) -> None:
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
        self._last_speculative_text = text

        def _runner():
            from app.operators.agent_intelligence import get_agent_intelligence

            intelligence = get_agent_intelligence()
            _, history = messages_from_context(self._llm_context) if self._llm_context else ("", [])
            return intelligence.execute_task_streaming(
                settings=self._app_settings,
                org_id=self._org_id,
                user_id=self._user_id,
                query=text,
                agent_id=str(self._agent.get("id") or "") or None,
                conversation_history=history or None,
                conversation_id=self._conversation_id,
                spoken_mode=True,
                mode="fast",
            )

        run = start_speculative_run(text=text, runner=_runner, create_task=self.create_task)
        self._speculative_coordinator.set_run(run)
        logger.info(
            "pipecat_voice_speculative_generation_started org_id=%s chars=%s",
            self._org_id,
            len(text),
        )

    async def _prefetch(self, text: str) -> None:
        try:
            from app.services.chat_dialogue_settings import load_chat_dialogue_settings
            from app.services.sentiment_friction_service import get_sentiment_friction_service
            from app.services.unified_turn_tool_retrieval import (
                is_task_shaped_for_retrieval,
                warm_tool_document_embeddings,
            )
            from app.workflows.repository import get_supabase_client

            client = get_supabase_client(self._app_settings)
            await load_chat_dialogue_settings(self._org_id, self._app_settings, client=client)
            get_sentiment_friction_service().analyze(text, None)

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
                    from app.services.unified_retrieval_service import UnifiedRetrievalService

                    svc = UnifiedRetrievalService(self._app_settings)
                    await svc.retrieve_knowledge_rows(
                        org_id=self._org_id,
                        query=query,
                        top_k=4,
                        agent_id=str(self._agent.get("id") or "") or None,
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
