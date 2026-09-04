"""Speculative prefetch on interim STT — starts RECALL-friendly warm work early.

Does not bypass CognitiveTurnKernel. On InterimTranscriptionFrame with stable
partial text, kick off a background coroutine that can warm caches; the real
turn still runs through GravitreCognitiveLLMService on final context.
"""
from __future__ import annotations

import asyncio
from typing import Any

from pipecat.frames.frames import Frame, InterimTranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.core.logging import get_logger

logger = get_logger(__name__)


class SpeculativePrefetchProcessor(FrameProcessor):
    """Fire-and-forget warm path on high-confidence interim transcripts."""

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
            # Lightweight warm: org dialogue settings + sentiment (no Fabric merge).
            from app.services.chat_dialogue_settings import load_chat_dialogue_settings
            from app.services.sentiment_friction_service import get_sentiment_friction_service
            from app.workflows.repository import get_supabase_client

            client = get_supabase_client(self._app_settings)
            await load_chat_dialogue_settings(self._org_id, self._app_settings, client=client)
            get_sentiment_friction_service().analyze(text, None)
            logger.debug(
                "pipecat_speculative_prefetch org_id=%s chars=%s",
                self._org_id,
                len(text),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.debug("pipecat_speculative_prefetch_failed error=%s", exc)
