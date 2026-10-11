"""Every assistant_text delta the bridge emits is labelled filler, progress or answer."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from pipecat.frames.frames import OutputTransportMessageUrgentFrame

from app.config import Settings
from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
from app.services.pipecat_voice.voice_reply_playback import VoicePlaybackTracker
from app.services.pipecat_voice.voice_silence_guard import DEEP_ACKNOWLEDGEMENTS
from app.services.shared_turn_preparation import TurnGuardrailBlocked

DEEP_TEXT = "send an email to acme about the renewal timeline"


def _service(**settings: Any) -> GravitreCognitiveLLMService:
    return GravitreCognitiveLLMService(
        app_settings=SimpleNamespace(voice_slow_tool_notice_seconds=0, **settings),
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
    )


def _run(events: list[Any], *, delay_s: float = 0.0, ack_s: float = 0.05, guard: Any = None) -> tuple[list[dict], dict]:
    async def _fake_stream(**_kwargs: Any):
        yield AssistantStreamEvent(sse_type="data-intelligence", payload={"data": {}})
        await asyncio.sleep(delay_s)
        for event in events:
            yield event
        yield AssistantStreamComplete(full_content="", tool_results=[], react_result=None, model="test")

    fake_intelligence = type("FakeIntelligence", (), {"execute_task_streaming": staticmethod(_fake_stream)})()
    service = _service(voice_deep_ack_seconds=ack_s)
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
        "app.services.shared_turn_preparation.guard_spoken_turn", new=guard or AsyncMock(return_value=None)
    ), patch("app.services.shared_turn_preparation.build_turn_system_prompt", return_value=""):
        asyncio.run(service._run_gravitre_turn(_FakeContext()))
    return [m for m in messages if m.get("type") == "assistant_text"], extras


def test_ack_is_filler_tool_narration_is_progress_and_text_is_answer() -> None:
    events = [
        AssistantStreamEvent(
            sse_type="tool-input-available", payload={"toolCallId": "c1", "toolName": "searchCrmRecords"}
        ),
        AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Renewal is in March. "}),
        AssistantStreamEvent(sse_type="tool-output-available", payload={"toolCallId": "c1", "output": {}}),
        AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Want me to draft it?"}),
    ]
    deltas, extras = _run(events, delay_s=0.3)
    kinds = [(m["kind"], m["delta"].strip()) for m in deltas]
    assert kinds[0][0] == "filler" and kinds[0][1] in DEEP_ACKNOWLEDGEMENTS
    assert any(kind == "progress" for kind, _ in kinds)
    answer = "".join(m["delta"] for m in deltas if m["kind"] == "answer")
    assert "Renewal is in March." in answer and "Want me to draft it?" in answer
    assert all(m["kind"] in {"filler", "progress", "answer"} for m in deltas)
    # Chunking evidence: the first answer sentence went out while the tool ran.
    assert extras["answer_chunks_while_tool_pending"] == 1
    assert extras["tool_calls"] == 1


def test_spoken_refusal_is_the_answer() -> None:
    guard = AsyncMock(side_effect=TurnGuardrailBlocked("budget_exceeded"))
    deltas, _ = _run([], guard=guard)
    assert [m["kind"] for m in deltas] == ["answer"]
    assert deltas[0]["delta"].strip() == TurnGuardrailBlocked("budget_exceeded").spoken


def test_socket_history_drops_spoken_filler_and_rewrites_follow_the_store() -> None:
    service = _service()
    tracker = VoicePlaybackTracker(reply_id_getter=lambda: 1)
    tracker.note_assistant_text("Sure, let me look. ", "filler")
    tracker.note_assistant_text("Let me check your CRM. ", "progress")
    service._playback_tracker = tracker
    history = [
        {"role": "user", "content": "How did revenue do?"},
        {"role": "assistant", "content": "Sure let me look. Let me check your CRM. Revenue was up."},
        {"role": "assistant", "content": "Sure, let me look."},
    ]
    assert service._strip_spoken_fillers(history) == [
        {"role": "user", "content": "How did revenue do?"},
        {"role": "assistant", "content": "Revenue was up."},
    ]

    service._durable_live_rows = [
        {"role": "assistant", "content": "Revenue was up. Churn fell.", "_id": "a1"},
        {"role": "user", "content": "And churn?", "_id": "u2"},
    ]
    service.patch_live_assistant_row("a1", "Revenue was up.")
    rows = service._durable_rows()
    assert rows[0]["content"] == "Revenue was up."
    # Row ids stay internal: never part of the history given to the brain.
    assert all("_id" not in row for row in rows)


def test_playback_grounded_history_flag_defaults_off() -> None:
    assert Settings.model_fields["voice_playback_grounded_history_v1"].default is False
