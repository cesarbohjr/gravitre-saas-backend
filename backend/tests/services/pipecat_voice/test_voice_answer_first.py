"""voice_answer_first_v1: filler / progress lines never queue ahead of the answer."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pipecat.frames.frames import InterruptionFrame, OutputTransportMessageUrgentFrame, TTSAudioRawFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.config import Settings
from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
from app.services.pipecat_voice.voice_answer_first import (
    AUDIO_QUIET_S,
    RELEASE_LEAD_S,
    AnswerFirstSpeech,
    PlayoutClock,
    PlayoutClockProcessor,
)


class _Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def _scheduler(clock: _Clock, playout: PlayoutClock) -> tuple[AnswerFirstSpeech, list[tuple[str, str]]]:
    spoken: list[tuple[str, str]] = []

    async def _speak(text: str, kind: str) -> None:
        spoken.append((kind, text))

    return AnswerFirstSpeech(speak=_speak, playout=playout, clock=clock), spoken


def test_playout_clock_tracks_queued_audio_and_resets_on_flush() -> None:
    clock = _Clock()
    playout = PlayoutClock(clock=clock)
    assert playout.remaining() == 0.0
    playout.note_audio(1.0)
    playout.note_audio(0.5)
    assert playout.remaining() == pytest.approx(1.5)
    clock.t += 1.0
    assert playout.remaining() == pytest.approx(0.5)
    playout.reset()
    assert playout.remaining() == 0.0


def test_playout_processor_feeds_the_clock_and_resets_on_interruption() -> None:
    async def _go() -> None:
        clock = _Clock()
        playout = PlayoutClock(clock=clock)
        proc = PlayoutClockProcessor(playout)
        await BaseObject.setup(proc, TaskManager())
        proc.push_frame = AsyncMock()  # type: ignore[method-assign]
        await proc.process_frame(TTSAudioRawFrame(b"\x00\x00" * 24000, 24000, 1), FrameDirection.DOWNSTREAM)
        assert playout.remaining() == pytest.approx(1.0)
        await proc.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
        assert playout.remaining() == 0.0
        assert proc.push_frame.await_count == 2

    asyncio.run(_go())


def test_lines_are_released_one_at_a_time_as_queued_audio_runs_out() -> None:
    async def _go() -> None:
        clock = _Clock()
        playout = PlayoutClock(clock=clock)
        sched, spoken = _scheduler(clock, playout)
        sched.enqueue("Okay, give me a sec.", "filler")
        sched.enqueue("Let me check your CRM.", "progress")
        assert await sched.release_due() is True  # nothing queued: first line goes now
        assert spoken == [("filler", "Okay, give me a sec.")]
        # Its audio has not arrived yet: the next line waits.
        assert await sched.release_due() is False
        playout.note_audio(1.5)
        clock.t += AUDIO_QUIET_S  # the TTS finished the line
        assert await sched.release_due() is False  # 1.25 s still queued
        clock.t += 1.25 - RELEASE_LEAD_S + 0.01
        assert await sched.release_due() is True
        assert spoken[-1] == ("progress", "Let me check your CRM.")

    asyncio.run(_go())


def test_answer_drops_every_line_not_yet_released() -> None:
    async def _go() -> None:
        clock = _Clock()
        playout = PlayoutClock(clock=clock)
        playout.note_audio(5.0)  # a long line is playing
        sched, spoken = _scheduler(clock, playout)
        sched.enqueue("Let me check your CRM.", "progress")
        sched.enqueue("I found 3 of them.", "progress")
        assert sched.mark_answer_ready() == 2
        assert not sched.has_pending()
        # After the answer: filler / result lines are dropped outright...
        assert sched.enqueue("Okay, one moment.", "filler") is False
        assert sched.enqueue("I found 2 more.", "progress") is False
        # ...a line about work still running waits behind the answer audio.
        running = {"yes": True}
        assert sched.enqueue("Still checking the CRM.", "progress", lambda: running["yes"]) is True
        clock.t += 5.0
        assert await sched.release_due() is True
        assert spoken == [("progress", "Still checking the CRM.")]
        assert sched.stats.dropped_for_answer == 4

    asyncio.run(_go())


def test_a_tool_line_is_dropped_when_its_tool_finished_before_it_could_play() -> None:
    async def _go() -> None:
        clock = _Clock()
        playout = PlayoutClock(clock=clock)
        playout.note_audio(2.0)
        sched, spoken = _scheduler(clock, playout)
        running = {"crm": True}
        sched.enqueue("Let me check your CRM.", "progress", lambda: running["crm"])
        sched.enqueue("I found 3 of them.", "progress")
        running["crm"] = False
        clock.t += 2.0
        assert await sched.release_due() is True
        assert spoken == [("progress", "I found 3 of them.")]
        assert sched.stats.dropped_stale == 1

    asyncio.run(_go())


def test_a_result_line_waits_out_its_grace_and_a_repeat_is_not_said_again() -> None:
    async def _go() -> None:
        clock = _Clock()
        playout = PlayoutClock(clock=clock)
        sched, spoken = _scheduler(clock, playout)
        sched.enqueue("I found 3 of them.", "progress", hold_s=1.0)
        assert await sched.release_due() is False  # the answer may still come
        clock.t += 1.0
        assert await sched.release_due() is True
        sched.enqueue("I found 3  of them.", "progress")
        clock.t += 5.0
        assert await sched.release_due() is False
        assert spoken == [("progress", "I found 3 of them.")]
        assert sched.stats.dropped_repeat == 1

    asyncio.run(_go())


def test_finish_turn_says_what_is_still_true_when_there_was_no_answer() -> None:
    async def _go() -> None:
        clock = _Clock()
        playout = PlayoutClock(clock=clock)
        playout.note_audio(10.0)
        sched, spoken = _scheduler(clock, playout)
        sched.enqueue("Let me check analytics.", "progress", lambda: False)
        sched.enqueue("I couldn't reach analytics.", "progress")
        await sched.finish_turn()
        assert spoken == [("progress", "I couldn't reach analytics.")]

    asyncio.run(_go())


# ---- the LLM bridge ---------------------------------------------------------

DEEP_TEXT = "send an email to acme about the renewal timeline"


class _BusyPlayout:
    """A speaker with plenty queued: nothing held is due."""

    audio_frames = 0

    def remaining(self) -> float:
        return 10.0

    def quiet_for(self) -> float:
        return 10.0


def _run_turn(events: list[Any], *, answer_first: bool) -> tuple[list[dict], dict]:
    async def _fake_stream(**_kwargs: Any):
        yield AssistantStreamEvent(sse_type="data-intelligence", payload={"data": {}})
        await asyncio.sleep(0.3)
        for event in events:
            yield event
            await asyncio.sleep(0)
        yield AssistantStreamComplete(full_content="", tool_results=[], react_result=None, model="test")

    fake_intelligence = type("FakeIntelligence", (), {"execute_task_streaming": staticmethod(_fake_stream)})()
    service = GravitreCognitiveLLMService(
        app_settings=SimpleNamespace(
            voice_slow_tool_notice_seconds=0, voice_deep_ack_seconds=0.05, voice_answer_first_v1=answer_first
        ),
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
    )
    service._playout_clock = _BusyPlayout()
    messages: list[dict] = []
    extras: dict[str, Any] = {}

    async def _push(frame: Any, *_a: Any, **_k: Any) -> None:
        if isinstance(frame, OutputTransportMessageUrgentFrame) and isinstance(frame.message, dict):
            messages.append(frame.message)

    service.push_frame = AsyncMock(side_effect=_push)
    service.start_ttfb_metrics = AsyncMock()
    service.stop_ttfb_metrics = AsyncMock()
    service._push_narration_speech = AsyncMock()  # type: ignore[method-assign]
    service._push_llm_text = AsyncMock()  # type: ignore[method-assign]

    class _Trace:
        def begin_turn(self) -> None: ...
        def note(self, *_a: Any, **_k: Any) -> None: ...
        def set_turn_meta(self, **_k: Any) -> None: ...
        def attach_intelligence(self, *_a: Any) -> None: ...

        def add_extra(self, key: str, value: Any) -> None:
            extras[key] = value

    service._turn_trace = _Trace()

    class _FakeContext:
        def get_messages(self) -> list[dict[str, Any]]:
            return [{"role": "user", "content": DEEP_TEXT}]

    with patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=fake_intelligence), patch(
        "app.services.shared_turn_preparation.guard_spoken_turn", new=AsyncMock(return_value=None)
    ), patch("app.services.shared_turn_preparation.build_turn_system_prompt", return_value=""):
        async def _turn() -> None:
            await service._run_gravitre_turn(_FakeContext())
            # process_frame's finally does this for every turn.
            await service._stop_answer_first()

        asyncio.run(_turn())
    assert service._answer_first is None and service._answer_first_task is None
    return [m for m in messages if m.get("type") == "assistant_text"], extras


TOOL_THEN_ANSWER = [
    AssistantStreamEvent(sse_type="tool-input-available", payload={"toolCallId": "c1", "toolName": "searchCrmRecords"}),
    AssistantStreamEvent(sse_type="tool-output-available", payload={"toolCallId": "c1", "output": {}}),
    AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Renewal is in March. "}),
    AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Want me to draft it?"}),
]


def test_flag_on_held_lines_are_dropped_when_the_answer_is_ready() -> None:
    deltas, extras = _run_turn(TOOL_THEN_ANSWER, answer_first=True)
    # Nothing held was ever shown or spoken; the answer is unchanged.
    assert [m["kind"] for m in deltas] == ["answer"] * len(deltas)
    assert "".join(m["delta"] for m in deltas) == "Renewal is in March. Want me to draft it?"
    stats = extras["answer_first"]
    assert stats["released"] == 0 and stats["dropped_for_answer"] >= 2


def test_flag_off_speaks_every_line_as_before() -> None:
    deltas, extras = _run_turn(TOOL_THEN_ANSWER, answer_first=False)
    kinds = [m["kind"] for m in deltas]
    assert kinds[0] == "filler" and "progress" in kinds
    assert "".join(m["delta"] for m in deltas if m["kind"] == "answer") == "Renewal is in March. Want me to draft it?"
    assert "answer_first" not in extras


def test_flag_on_a_turn_with_no_answer_text_still_says_its_result_line() -> None:
    events = [
        AssistantStreamEvent(sse_type="tool-input-available", payload={"toolCallId": "c1", "toolName": "searchCrmRecords"}),
        AssistantStreamEvent(sse_type="tool-output-available", payload={"toolCallId": "c1", "output": {"error": "x"}}),
    ]
    off, _ = _run_turn(events, answer_first=False)
    on, extras = _run_turn(events, answer_first=True)
    off_progress = [m["delta"] for m in off if m["kind"] == "progress"]
    on_progress = [m["delta"] for m in on if m["kind"] == "progress"]
    # "Let me check X" is dropped (X already finished); any result line is kept.
    assert len(on_progress) == len(off_progress) - 1
    assert set(on_progress) <= set(off_progress)
    assert extras["answer_first"]["dropped_stale"] >= 1


def test_answer_first_flag_defaults_off() -> None:
    assert Settings.model_fields["voice_answer_first_v1"].default is False
