"""GravitreCognitiveLLMService — Pipecat LLM bridge to CognitiveTurnKernel.

Never uses Pipecat's default OpenAI LLM. All reasoning goes through
`execute_task_streaming(..., spoken_mode=True)` so write governance, memory,
Knowledge Fabric depth tiering, Module C honesty, and spoken register stay intact.
"""
from __future__ import annotations

import time
from typing import Any

from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    OutputTransportMessageUrgentFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.llm_service import LLMService

from app.core.logging import get_logger
from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services.voice_session_service import normalize_spoken_text, split_speakable_chunks

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
        first_delta_at: float | None = None
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
            if event.sse_type == "data-intelligence":
                # Voice latency instrumentation (2026-09-04): the Pipecat bridge
                # previously discarded this event entirely, so the routing/
                # reasoning latency breakdown that unified-turn already
                # computes was never visible for voice turns. Log-only —
                # never sent to the client, zero behavior change.
                payload = event.payload if isinstance(event.payload, dict) else {}
                data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
                if isinstance(data, dict):
                    routing = data.get("routing") if isinstance(data.get("routing"), dict) else {}
                    logger.info(
                        "pipecat_voice_turn_latency org_id=%s pre_llm_ms=%s reasoning_depth=%s "
                        "routing_tier=%s effective_mode=%s model_ttft_ms=%s pre_model_ms=%s "
                        "wall_to_first_token_ms=%s cached_prompt_tokens=%s cognitive_stage_ms=%s",
                        self._org_id,
                        int((time.perf_counter() - turn_start) * 1000),
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
            if event.sse_type != "text-delta":
                continue
            if first_delta_at is None:
                first_delta_at = time.perf_counter()
                logger.info(
                    "pipecat_voice_turn_latency org_id=%s first_text_delta_ms=%s",
                    self._org_id,
                    int((first_delta_at - turn_start) * 1000),
                )
            payload = event.payload if isinstance(event.payload, dict) else {}
            delta = str(payload.get("delta") or payload.get("textDelta") or "")
            if not delta:
                continue
            await self.push_frame(
                OutputTransportMessageUrgentFrame(
                    message={"type": "assistant_text", "delta": delta}
                )
            )
            text_buffer += delta
            chunks, text_buffer = split_speakable_chunks(text_buffer)
            for chunk in chunks:
                spoken = normalize_spoken_text(chunk)
                if spoken:
                    await self._push_llm_text(spoken)
        # Flush any trailing clause that never hit a sentence boundary (e.g.
        # a short answer with no terminal punctuation) so the tail of the
        # reply is not silently dropped from speech.
        tail = normalize_spoken_text(text_buffer)
        if tail:
            await self._push_llm_text(tail)
