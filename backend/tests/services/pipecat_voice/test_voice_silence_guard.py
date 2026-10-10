"""Dead-air guard: one slow tool call no longer leaves a voice caller in silence.

Before 2026-10-07 nothing was said between a tool's start narration and its
result, however long the call took. The turn now speaks one honest
"still running" line once the call has been silent past the threshold, and
never speaks it for a call that already returned.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
from app.services.pipecat_voice.voice_silence_guard import (
    SILENCE_TICK,
    SlowToolNotices,
    slow_tool_notice_seconds,
    with_silence_ticks,
)
from app.services.pipecat_voice.voice_tool_narration import narrate_tool_still_running


def _tool_start(call_id: str, tool_name: str) -> AssistantStreamEvent:
    return AssistantStreamEvent(
        sse_type="tool-input-available",
        payload={"toolCallId": call_id, "toolName": tool_name, "input": {}},
    )


def _tool_output(call_id: str, output: dict[str, Any]) -> AssistantStreamEvent:
    return AssistantStreamEvent(
        sse_type="tool-output-available", payload={"toolCallId": call_id, "output": output}
    )


def _spoken_lines(events_and_delays: list[tuple[Any, float]], *, notice_s: float) -> list[str]:
    async def _fake_stream(**_kwargs: Any):
        for event, delay in events_and_delays:
            if delay:
                await asyncio.sleep(delay)
            yield event
        yield AssistantStreamComplete(full_content="", tool_results=[], react_result=None, model="test")

    fake_intelligence = type("FakeIntelligence", (), {"execute_task_streaming": staticmethod(_fake_stream)})()
    service = GravitreCognitiveLLMService(
        app_settings=SimpleNamespace(voice_slow_tool_notice_seconds=notice_s),
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
    )
    service.push_frame = AsyncMock()
    service._push_llm_text = AsyncMock()
    service.start_ttfb_metrics = AsyncMock()
    service.stop_ttfb_metrics = AsyncMock()
    spoken: list[str] = []

    async def _record(text: str) -> None:
        spoken.append(text)

    service._speak_narration = _record  # type: ignore[method-assign]

    class _FakeContext:
        def get_messages(self) -> list[dict[str, Any]]:
            return [{"role": "user", "content": "find the stalled deals"}]

    with patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=fake_intelligence):
        asyncio.run(service._run_gravitre_turn(_FakeContext()))
    return spoken


def test_slow_tool_gets_one_honest_still_running_line():
    spoken = _spoken_lines(
        [(_tool_start("c1", "searchDeals"), 0.0), (_tool_output("c1", {"results": []}), 0.35)],
        notice_s=0.1,
    )
    still = [line for line in spoken if line.startswith("Still")]
    assert still == [narrate_tool_still_running("searchDeals")]
    # It is said after the start narration and before anything about the result.
    assert spoken.index(still[0]) > 0


def test_fast_tool_gets_no_still_running_line():
    spoken = _spoken_lines(
        [(_tool_start("c1", "searchDeals"), 0.0), (_tool_output("c1", {"results": []}), 0.02)],
        notice_s=0.5,
    )
    assert not any("still" in line.lower() for line in spoken)


def test_silence_before_any_tool_is_not_narrated():
    """A slow model with no open tool call is not a tool to report on."""
    spoken = _spoken_lines([(AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Hi."}), 0.3)], notice_s=0.1)
    assert not any("still" in line.lower() for line in spoken)


def test_write_tool_uses_executing_phrasing():
    assert narrate_tool_still_running("updateDealStage").startswith("Still updating")
    assert narrate_tool_still_running("searchDeals", repeat=True) == "Still working on it."


def test_notices_are_spaced_and_capped_per_call():
    notices = SlowToolNotices(1.0)
    open_calls = {"c1": 0.0}
    names = {"c1": "searchDeals"}
    assert notices.due(open_calls, names, now=0.5) is None
    assert notices.due(open_calls, names, now=1.0) == ("searchDeals", False)
    assert notices.due(open_calls, names, now=2.0) is None  # repeats wait 3x longer
    assert notices.due(open_calls, names, now=4.0) == ("searchDeals", True)
    assert notices.due(open_calls, names, now=7.0) == ("searchDeals", True)
    assert notices.due(open_calls, names, now=100.0) is None  # capped
    # Connector-status checks never narrate.
    assert SlowToolNotices(1.0).due({"c2": 0.0}, {"c2": "getConnectorStatus"}, now=5.0, skip=lambda n: True) is None


def test_ticks_do_not_cancel_the_pending_event():
    async def _source():
        await asyncio.sleep(0.25)
        yield "event"

    async def _collect() -> list[Any]:
        return [item async for item in with_silence_ticks(_source(), interval_s=0.1)]

    out = asyncio.run(_collect())
    assert out[-1] == "event" and out.count(SILENCE_TICK) >= 1


def test_threshold_defaults_and_can_be_disabled():
    assert slow_tool_notice_seconds(object()) == 4.0
    assert slow_tool_notice_seconds(SimpleNamespace(voice_slow_tool_notice_seconds=0)) == 0.0
