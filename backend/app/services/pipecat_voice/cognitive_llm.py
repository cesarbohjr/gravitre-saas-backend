"""GravitreCognitiveLLMService — Pipecat LLM bridge to CognitiveTurnKernel.

Never uses Pipecat's default OpenAI LLM. All reasoning goes through
`execute_task_streaming(..., spoken_mode=True)` so write governance, memory,
Knowledge Fabric depth tiering, Module C honesty, and spoken register stay intact.
"""
from __future__ import annotations

from typing import Any

from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.llm_service import LLMService

from app.core.logging import get_logger
from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services.voice_session_service import normalize_spoken_text

logger = get_logger(__name__)


def _messages_from_context(context: Any) -> tuple[str, list[dict[str, Any]]]:
    """Extract latest user text + prior history from LLMContext."""
    messages: list[dict[str, Any]] = []
    get_messages = getattr(context, "get_messages", None)
    raw = get_messages() if callable(get_messages) else getattr(context, "messages", None) or []
    for m in raw or []:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "").strip().lower()
        content = m.get("content")
        if isinstance(content, list):
            text_parts = [
                str(p.get("text") or "")
                for p in content
                if isinstance(p, dict) and p.get("type") in {None, "text", "input_text"}
            ]
            content = " ".join(t for t in text_parts if t).strip()
        text = str(content or "").strip()
        if role in {"user", "assistant"} and text:
            messages.append({"role": role, "content": text})
    user_text = ""
    for m in reversed(messages):
        if m["role"] == "user":
            user_text = m["content"]
            break
    history = messages[:-1] if messages and messages[-1]["role"] == "user" else messages
    return user_text, history


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
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        # Never assign to self._settings — AIService owns that for Pipecat ServiceSettings.
        self._app_settings = app_settings
        self._org_id = org_id
        self._user_id = user_id
        self._agent = agent
        self._conversation_id = conversation_id

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMContextFrame):
            await self.push_frame(LLMFullResponseStartFrame())
            try:
                await self.start_processing_metrics()
                await self._run_gravitre_turn(frame.context)
            except Exception as exc:  # noqa: BLE001
                logger.exception("pipecat_cognitive_llm_failed error=%s", exc)
                await self.push_error(error_msg=str(exc)[:500], exception=exc)
                await self.push_frame(ErrorFrame(error=str(exc)[:500]))
            finally:
                await self.stop_processing_metrics()
                await self.push_frame(LLMFullResponseEndFrame())
            return
        await self.push_frame(frame, direction)

    async def _run_gravitre_turn(self, context: Any) -> None:
        from app.operators.agent_intelligence import get_agent_intelligence

        user_text, history = _messages_from_context(context)
        if not user_text:
            return
        intelligence = get_agent_intelligence()
        async for event in intelligence.execute_task_streaming(
            settings=self._app_settings,
            org_id=self._org_id,
            user_id=self._user_id,
            query=user_text,
            agent_id=str((self._agent or {}).get("id") or "") or None,
            conversation_history=history or None,
            conversation_id=self._conversation_id,
            spoken_mode=True,
            mode="fast",
        ):
            if isinstance(event, AssistantStreamComplete):
                continue
            if not isinstance(event, AssistantStreamEvent):
                continue
            if event.sse_type != "text-delta":
                continue
            payload = event.payload if isinstance(event.payload, dict) else {}
            delta = str(payload.get("delta") or payload.get("textDelta") or "")
            if not delta:
                continue
            spoken = normalize_spoken_text(delta)
            if spoken:
                await self._push_llm_text(spoken)
