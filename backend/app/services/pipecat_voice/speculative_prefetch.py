"""Speculative prefetch on interim STT — READ-only warm work early.

Does not bypass CognitiveTurnKernel. Never executes tools or consequential
writes. On InterimTranscriptionFrame with stable partial text:
  1) warm dialogue settings + sentiment
  2) if task-shaped, warm tool-retrieval query embedding cache (READ only)

Cancel-and-restart when the partial changes (composes with barge-in / Flux EOT).
"""
from __future__ import annotations

import asyncio
from typing import Any

from pipecat.frames.frames import Frame, InterimTranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.core.logging import get_logger

logger = get_logger(__name__)


class SpeculativePrefetchProcessor(FrameProcessor):
    """Fire-and-forget READ-only warm path on high-confidence interim transcripts."""

    def __init__(
        self,
        *,
        app_settings: Any,
        org_id: str,
        user_id: str,
        min_chars: int = 12,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._app_settings = app_settings
        self._org_id = org_id
        self._user_id = user_id
        self._min_chars = min_chars
        self._last_partial = ""
        self._task: asyncio.Task[None] | None = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, InterimTranscriptionFrame):
            text = (frame.text or "").strip()
            if len(text) >= self._min_chars and text != self._last_partial:
                self._last_partial = text
                if self._task and not self._task.done():
                    self._task.cancel()
                self._task = self.create_task(self._prefetch(text))
        await self.push_frame(frame, direction)

    async def _prefetch(self, text: str) -> None:
        try:
            from app.services.chat_dialogue_settings import load_chat_dialogue_settings
            from app.services.sentiment_friction_service import get_sentiment_friction_service
            from app.services.unified_turn_tool_retrieval import is_task_shaped_for_retrieval
            from app.workflows.repository import get_supabase_client

            client = get_supabase_client(self._app_settings)
            await load_chat_dialogue_settings(self._org_id, self._app_settings, client=client)
            get_sentiment_friction_service().analyze(text, None)

            use_emb, shape, query = is_task_shaped_for_retrieval(text)
            embed_warmed = False
            if use_emb and len((query or "").strip()) >= self._min_chars:
                # READ-only: warm query embedding cache. Never invoke tools / writes.
                from app.rag.tool_retrieval_embedding import embed_tool_retrieval_query_timed

                await asyncio.to_thread(
                    embed_tool_retrieval_query_timed,
                    query,
                    self._app_settings,
                )
                embed_warmed = True

            logger.info(
                "pipecat_speculative_prefetch org_id=%s chars=%s shape=%s embed_warmed=%s write_exec=false",
                self._org_id,
                len(text),
                shape,
                embed_warmed,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.debug("pipecat_speculative_prefetch_failed error=%s", exc)
