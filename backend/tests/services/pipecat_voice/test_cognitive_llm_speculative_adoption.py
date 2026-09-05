"""Voice-SLO follow-up (2026-09-05): GravitreCognitiveLLMService adopting a
matching speculative run at confirmed end-of-turn instead of re-running
execute_task_streaming() from scratch — the actual latency win half of
"genuine, cancelable LLM generation on probable-EOT".
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.operators.stream_events import AssistantStreamEvent
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
from app.services.pipecat_voice.speculative_generation import (
    SpeculativeGenerationCoordinator,
    start_speculative_run,
)


def _text_delta(text: str) -> AssistantStreamEvent:
    return AssistantStreamEvent(sse_type="text-delta", payload={"delta": text})


class _FakeContext:
    def get_messages(self) -> list[dict[str, Any]]:
        return [{"role": "user", "content": "what is two plus two"}]


def _service(coordinator: SpeculativeGenerationCoordinator | None) -> tuple[
    GravitreCognitiveLLMService, list[str], list[str]
]:
    service = GravitreCognitiveLLMService(
        app_settings=object(),
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
        speculative_coordinator=coordinator,
    )
    display_deltas: list[str] = []
    tts_chunks: list[str] = []

    async def _capture_push_frame(frame: Any, *_a: Any, **_kw: Any) -> None:
        message = getattr(frame, "message", None)
        if isinstance(message, dict) and message.get("type") == "assistant_text":
            display_deltas.append(str(message.get("delta") or ""))

    async def _capture_push_llm_text(text: str) -> None:
        tts_chunks.append(text)

    service.push_frame = AsyncMock(side_effect=_capture_push_frame)
    service._push_llm_text = AsyncMock(side_effect=_capture_push_llm_text)
    service.start_ttfb_metrics = AsyncMock()
    service.stop_ttfb_metrics = AsyncMock()
    return service, display_deltas, tts_chunks


class TestMatchingSpeculativeRunIsAdoptedInsteadOfARefreshCall:
    @pytest.mark.asyncio
    async def test_execute_task_streaming_is_never_called_on_a_matched_adoption(self):
        """MUTATION PROOF: remove the adopt() check (always call
        execute_task_streaming fresh) and this test fails — the mock records
        a call.
        """
        coordinator = SpeculativeGenerationCoordinator()
        run = start_speculative_run(
            text="what is two plus two",
            runner=lambda: _events(_text_delta("Four.")),
            create_task=asyncio.ensure_future,
        )
        coordinator.set_run(run)
        await run.task

        service, display, tts = _service(coordinator)

        with patch(
            "app.operators.agent_intelligence.get_agent_intelligence",
        ) as mock_get_intel:
            mock_get_intel.return_value.execute_task_streaming = AsyncMock(
                side_effect=AssertionError("must not be called — speculative run should be adopted")
            )
            await service._run_gravitre_turn(_FakeContext())

        assert any("four" in d.lower() for d in display)
        assert any("four" in c.lower() for c in tts)

    @pytest.mark.asyncio
    async def test_adopted_run_still_drives_the_exact_same_narration_and_tts_pipeline(self):
        """The replayed events must go through identical processing to a
        live call — tool narration, text chunking, everything downstream of
        the event loop is untouched by which source produced the events.
        """
        coordinator = SpeculativeGenerationCoordinator()

        async def _events_seq():
            yield AssistantStreamEvent(
                sse_type="tool-input-available",
                payload={"toolCallId": "c1", "toolName": "getPipelineHealth", "input": {}},
            )
            yield AssistantStreamEvent(
                sse_type="tool-output-available",
                payload={"toolCallId": "c1", "output": {"results": [1, 2, 3]}},
            )
            yield _text_delta("Found three opportunities.")

        run = start_speculative_run(
            text="what is two plus two", runner=_events_seq, create_task=asyncio.ensure_future
        )
        coordinator.set_run(run)
        await run.task

        service, display, tts = _service(coordinator)
        with patch("app.operators.agent_intelligence.get_agent_intelligence") as mock_get_intel:
            mock_get_intel.return_value.execute_task_streaming = AsyncMock(
                side_effect=AssertionError("must not be called")
            )
            await service._run_gravitre_turn(_FakeContext())

        assert any("pipeline" in c.lower() for c in tts)  # tool-start narration
        assert any("found three" in c.lower() or "three opportunities" in c.lower() for c in tts)


class TestNoMatchFallsBackToAFreshCall:
    @pytest.mark.asyncio
    async def test_mismatched_pending_run_still_calls_execute_task_streaming_fresh(self):
        """Regression guard: a coordinator with a NON-matching pending run
        (the user said something different from what was speculated) must
        fall back to the exact same fresh call as if no coordinator existed
        at all — zero behavior change on the default/mismatch path.
        """
        coordinator = SpeculativeGenerationCoordinator()
        run = start_speculative_run(
            text="completely different guess",
            runner=lambda: _events(_text_delta("wrong answer")),
            create_task=asyncio.ensure_future,
        )
        coordinator.set_run(run)
        await run.task

        service, display, tts = _service(coordinator)

        async def _fresh_stream(**_kwargs: Any):
            yield _text_delta("Four.")

        with patch("app.operators.agent_intelligence.get_agent_intelligence") as mock_get_intel:
            mock_get_intel.return_value.execute_task_streaming = _fresh_stream
            await service._run_gravitre_turn(_FakeContext())

        assert any("four" in d.lower() for d in display)
        assert not any("wrong answer" in d.lower() for d in display)

    @pytest.mark.asyncio
    async def test_no_coordinator_configured_behaves_exactly_as_before(self):
        service, display, tts = _service(None)

        async def _fresh_stream(**_kwargs: Any):
            yield _text_delta("Four.")

        with patch("app.operators.agent_intelligence.get_agent_intelligence") as mock_get_intel:
            mock_get_intel.return_value.execute_task_streaming = _fresh_stream
            await service._run_gravitre_turn(_FakeContext())

        assert any("four" in d.lower() for d in display)


async def _events(*items):
    for item in items:
        yield item
