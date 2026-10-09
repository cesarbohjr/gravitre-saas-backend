"""Deep spoken turns acknowledge the caller early when the answer is slow.

A deep turn runs routing, the kernel and context assembly before its first
token, which left seconds of silence after the caller stopped talking. When
nothing has been said shortly after the turn is confirmed, the bridge speaks
one short acknowledgement with no data in it. Medium turns get the same
acknowledgement on the same timer (their first token is seconds away too).
Light turns, backing off ("never mind"), an answer that arrives in time, and a
refused turn say nothing extra.
"""
from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
from app.services.pipecat_voice.voice_silence_guard import (
    ACK_DUE,
    DEEP_ACKNOWLEDGEMENTS,
    deep_ack_seconds,
    pick_deep_acknowledgement,
    with_ack_deadline,
)
from app.services.shared_turn_preparation import TurnGuardrailBlocked

DEEP_TEXT = "send an email to acme about the renewal timeline"
MEDIUM_TEXT = "explain how vector databases work"
LIGHT_TEXT = "haha that's funny"
DECLINE_TEXT = "never mind"


def _turn(user_text: str, *, first_text_after_s: float, ack_s: float = 0.05, guard: Any = None) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    """Run one bridge turn; return (narrations spoken, answer chunks pushed), in order."""
    order: list[tuple[str, str]] = []

    async def _fake_stream(**_kwargs: Any):
        yield AssistantStreamEvent(sse_type="data-intelligence", payload={"data": {}})
        await asyncio.sleep(first_text_after_s)
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Who should receive it?"})
        yield AssistantStreamComplete(full_content="", tool_results=[], react_result=None, model="test")

    fake_intelligence = type("FakeIntelligence", (), {"execute_task_streaming": staticmethod(_fake_stream)})()
    service = GravitreCognitiveLLMService(
        app_settings=SimpleNamespace(voice_slow_tool_notice_seconds=0, voice_deep_ack_seconds=ack_s),
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
    )
    service.push_frame = AsyncMock()
    service.start_ttfb_metrics = AsyncMock()
    service.stop_ttfb_metrics = AsyncMock()

    async def _narration(text: str) -> None:
        order.append(("narration", text))

    async def _answer(text: str) -> None:
        order.append(("answer", text))

    service._push_narration_speech = _narration  # type: ignore[method-assign]
    service._push_llm_text = _answer  # type: ignore[method-assign]

    class _FakeContext:
        def get_messages(self) -> list[dict[str, Any]]:
            return [{"role": "user", "content": user_text}]

    with patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=fake_intelligence), patch(
        "app.services.shared_turn_preparation.guard_spoken_turn", new=guard or AsyncMock(return_value=None)
    ), patch("app.services.shared_turn_preparation.build_turn_system_prompt", return_value=""):
        asyncio.run(service._run_gravitre_turn(_FakeContext()))
    return [t for k, t in order if k == "narration"], [t for k, t in order if k == "answer"], order


def test_slow_deep_turn_is_acknowledged_before_the_answer() -> None:
    narrations, answers, order = _turn(DEEP_TEXT, first_text_after_s=0.3)
    assert len(narrations) == 1
    assert narrations[0] in DEEP_ACKNOWLEDGEMENTS
    assert answers and order[0] == ("narration", narrations[0])


def test_deep_answer_that_arrives_in_time_gets_no_acknowledgement() -> None:
    narrations, answers, _ = _turn(DEEP_TEXT, first_text_after_s=0.0, ack_s=0.5)
    assert narrations == []
    assert answers


def test_slow_medium_turn_is_acknowledged_like_deep() -> None:
    narrations, answers, order = _turn(MEDIUM_TEXT, first_text_after_s=0.3)
    assert len(narrations) == 1
    assert narrations[0] in DEEP_ACKNOWLEDGEMENTS
    assert answers and order[0] == ("narration", narrations[0])


def test_light_and_backing_off_turns_are_never_acknowledged() -> None:
    for text in (LIGHT_TEXT, DECLINE_TEXT):
        narrations, answers, _ = _turn(text, first_text_after_s=0.3)
        assert narrations == [], text
        assert answers


def test_refused_turn_speaks_only_the_refusal() -> None:
    guard = AsyncMock(side_effect=TurnGuardrailBlocked("budget_exceeded"))
    narrations, answers, _ = _turn(DEEP_TEXT, first_text_after_s=0.3, guard=guard)
    assert narrations == [TurnGuardrailBlocked("budget_exceeded").spoken]
    assert answers == []


def test_acknowledgements_carry_no_data_and_do_not_repeat_back_to_back() -> None:
    for line in DEEP_ACKNOWLEDGEMENTS:
        assert not re.search(r"\d", line)
        assert len(line.split()) <= 5
    previous = None
    for _ in range(50):
        current = pick_deep_acknowledgement(previous)
        assert current != previous
        previous = current


def test_ack_deadline_fires_once_without_cancelling_the_pending_event() -> None:
    async def _source():
        await asyncio.sleep(0.2)
        yield "first"
        await asyncio.sleep(0.2)
        yield "second"

    async def _collect() -> list[Any]:
        return [item async for item in with_ack_deadline(_source(), delay_s=0.05)]

    assert asyncio.run(_collect()) == [ACK_DUE, "first", "second"]


def test_ack_delay_defaults_and_can_be_disabled() -> None:
    assert deep_ack_seconds(object()) == 0.6
    assert deep_ack_seconds(SimpleNamespace(voice_deep_ack_seconds=0)) == 0.0
