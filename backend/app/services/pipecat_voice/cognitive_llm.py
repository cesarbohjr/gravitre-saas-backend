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
from app.services.pipecat_voice.llm_context_utils import messages_from_context as _messages_from_context
from app.services.pipecat_voice.speculative_generation import SpeculativeGenerationCoordinator
from app.services.pipecat_voice.voice_delivery_tags import strip_and_validate_delivery_tags
from app.services.pipecat_voice.voice_latency_metrics import record_voice_llm_stage_sample
from app.services.pipecat_voice.voice_tool_narration import (
    narrate_tool_completed,
    narrate_tool_started,
)
from app.services.voice_session_service import normalize_spoken_text, split_speakable_chunks

logger = get_logger(__name__)


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
        # Phase 2 (conversational-realism): progressive narration during
        # multi-step tool execution. Tracks toolCallId -> toolName from
        # tool-input-available so the matching tool-output-available (which
        # carries no toolName of its own) can still be narrated honestly.
        # Dedupe tool-started narration per tool name so a turn calling the
        # same tool twice doesn't repeat "Let me check X" — real state, said
        # once, not a chatty loop.
        tool_names_by_call_id: dict[str, str] = {}
        narrated_tool_starts: set[str] = set()
        first_delta_at: float | None = None
        first_speakable_chunk_at: float | None = None
        tts_requested_at: float | None = None
        # Phase 6 (conversational-realism): real TTFB metrics for the LLM
        # bridge itself. GravitreCognitiveLLMService never streams tokens
        # through Pipecat's stock LLM adapters, so this stage's TTFB is not
        # measured automatically anywhere else — start/stop it explicitly so
        # GravitreVoiceLatencyObserver (pipeline.py) actually receives a real
        # sample for this processor instead of silence.
        await self.start_ttfb_metrics()
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
            self._speculative_coordinator.adopt(user_text) if self._speculative_coordinator else None
        )
        if speculative_run is not None:
            logger.info(
                "pipecat_voice_speculative_generation_adopted org_id=%s chars=%s",
                self._org_id,
                len(user_text),
            )
            events_source = speculative_run.events()
        else:
            events_source = intelligence.execute_task_streaming(
                settings=self._app_settings,
                org_id=self._org_id,
                user_id=self._user_id,
                query=user_text,
                agent_id=str((self._agent or {}).get("id") or "") or None,
                conversation_history=history or None,
                conversation_id=self._conversation_id,
                spoken_mode=True,
                mode="fast",
            )
        async for event in events_source:
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
            if event.sse_type == "tool-input-available":
                payload = event.payload if isinstance(event.payload, dict) else {}
                call_id = str(payload.get("toolCallId") or "")
                tool_name = str(payload.get("toolName") or "")
                if call_id and tool_name:
                    tool_names_by_call_id[call_id] = tool_name
                if tool_name and tool_name not in narrated_tool_starts:
                    narrated_tool_starts.add(tool_name)
                    await self._speak_narration(narrate_tool_started(tool_name))
                continue
            if event.sse_type == "tool-output-available":
                payload = event.payload if isinstance(event.payload, dict) else {}
                call_id = str(payload.get("toolCallId") or "")
                tool_name = tool_names_by_call_id.get(call_id, "")
                narration = narrate_tool_completed(tool_name, payload.get("output"))
                if narration:
                    await self._speak_narration(narration)
                continue
            if event.sse_type != "text-delta":
                continue
            if first_delta_at is None:
                first_delta_at = time.perf_counter()
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
            await self.push_frame(
                OutputTransportMessageUrgentFrame(
                    message={"type": "assistant_text", "delta": delta}
                )
            )
            text_buffer += delta
            chunks, text_buffer = split_speakable_chunks(text_buffer)
            for chunk in chunks:
                spoken = self._sanitize_for_tts(chunk)
                if spoken:
                    if first_speakable_chunk_at is None:
                        first_speakable_chunk_at = time.perf_counter()
                    await self._push_llm_text(spoken)
                    if tts_requested_at is None:
                        tts_requested_at = time.perf_counter()
        # Flush any trailing clause that never hit a sentence boundary (e.g.
        # a short answer with no terminal punctuation) so the tail of the
        # reply is not silently dropped from speech.
        tail = self._sanitize_for_tts(text_buffer)
        if tail:
            if first_speakable_chunk_at is None:
                first_speakable_chunk_at = time.perf_counter()
            await self._push_llm_text(tail)
            if tts_requested_at is None:
                tts_requested_at = time.perf_counter()

        def _ms(at: float | None) -> int | None:
            return int((at - turn_start) * 1000) if at is not None else None

        record_voice_llm_stage_sample(
            self._app_settings,
            org_id=self._org_id,
            user_id=self._user_id,
            conversation_id=self._conversation_id,
            llm_first_token_ms=_ms(first_delta_at),
            llm_first_speakable_chunk_ms=_ms(first_speakable_chunk_at),
            tts_requested_ms=_ms(tts_requested_at),
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
            await self._push_llm_text(spoken)

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
        return normalize_spoken_text(scan.clean_text)
