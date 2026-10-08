"""The LLM bridge stamps its stages and the brain's checkpoints on the turn trace."""
from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, patch

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
from app.services.pipecat_voice.voice_turn_trace import VoiceTurnTrace


def test_one_turn_reaches_the_trace_with_brain_marks_tier_and_turn_id() -> None:
    seen_kwargs: dict[str, Any] = {}

    async def _fake_stream(**kwargs: Any):
        seen_kwargs.update(kwargs)
        marks = kwargs["latency_marks"]
        marks["_t0_perf"] = time.perf_counter()
        marks["client_ready"] = 0
        marks["pre_kernel_entry"] = 1
        marks["react_entry"] = 2
        yield AssistantStreamEvent(
            sse_type="data-intelligence",
            payload={"data": {"effectiveMode": "agent", "routing": {"reasoningDepth": "full"}}},
        )
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Done. "})
        yield AssistantStreamComplete(
            full_content="Done.", tool_results=[], react_result=None, model="test", message_id="m-1"
        )

    fake_intelligence = type("FakeIntelligence", (), {"execute_task_streaming": staticmethod(_fake_stream)})()
    service = GravitreCognitiveLLMService(
        app_settings=object(),
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
    )
    written: list[dict] = []
    service._turn_trace = VoiceTurnTrace(writer=written.append)
    service.push_frame = AsyncMock()
    service._push_llm_text = AsyncMock()
    service._persist_completed_voice_turn = lambda **_k: (None, None)

    class _Ctx:
        def get_messages(self) -> list[dict[str, Any]]:
            return [{"role": "user", "content": "send the report to the team"}]

    async def _turn() -> None:
        from pipecat.frames.frames import LLMContextFrame

        with patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=fake_intelligence):
            await service.process_frame(LLMContextFrame(context=_Ctx()), direction=None)  # type: ignore[arg-type]

    with (
        patch.object(GravitreCognitiveLLMService, "start_processing_metrics", AsyncMock()),
        patch.object(GravitreCognitiveLLMService, "stop_processing_metrics", AsyncMock()),
        patch.object(GravitreCognitiveLLMService, "start_ttfb_metrics", AsyncMock()),
        patch.object(GravitreCognitiveLLMService, "stop_ttfb_metrics", AsyncMock()),
        patch("pipecat.services.llm_service.LLMService.process_frame", AsyncMock()),
    ):
        asyncio.run(_turn())

    assert isinstance(seen_kwargs.get("latency_marks"), dict)
    assert len(written) == 1  # no audio left the server, so nothing to wait for
    rec = written[0]
    assert rec["turn_id"] == "m-1"
    assert rec["tier"] == "deep"
    d = rec["stage_durations_ms"]
    for stage in ("durable_context_ms", "prompt_assembly_ms", "brain_pre_llm_ms", "model_ttft_ms"):
        assert stage in d, stage
    assert d["brain.react_entry"] == 2
