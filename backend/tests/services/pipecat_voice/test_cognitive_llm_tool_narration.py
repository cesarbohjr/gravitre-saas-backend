"""Phase 2 (conversational-realism): progressive spoken narration during
multi-step tool execution.

Drives ``GravitreCognitiveLLMService._run_gravitre_turn`` with the exact
``tool-input-available`` / ``tool-output-available`` events the live
ReAct/multi-step execution path already yields (see
``app/operators/agent_intelligence.py`` -> ``sse_react_tool_start`` /
``sse_react_tool_complete`` in ``assistant_sse.py``) — the SAME event
stream already proven for the text plan-bar, not a hand-rolled shortcut.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService


def _drive(events: list[Any]) -> tuple[list[str], list[str]]:
    """Run one turn against a scripted event sequence; return (display, tts)."""

    async def _fake_stream(**_kwargs: Any):
        for event in events:
            yield event
        yield AssistantStreamComplete(
            full_content="final answer",
            tool_results=[],
            react_result=None,
            model="test",
        )

    fake_intelligence = type(
        "FakeIntelligence", (), {"execute_task_streaming": staticmethod(_fake_stream)}
    )()

    service = GravitreCognitiveLLMService(
        app_settings=object(),
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
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

    class _FakeContext:
        def get_messages(self) -> list[dict[str, Any]]:
            return [{"role": "user", "content": "check my pipeline"}]

    with patch(
        "app.operators.agent_intelligence.get_agent_intelligence",
        return_value=fake_intelligence,
    ):
        asyncio.run(service._run_gravitre_turn(_FakeContext()))

    return display_deltas, tts_chunks


def _tool_start(call_id: str, tool_name: str) -> AssistantStreamEvent:
    return AssistantStreamEvent(
        sse_type="tool-input-available",
        payload={"toolCallId": call_id, "toolName": tool_name, "input": {}},
    )


def _tool_output(call_id: str, output: dict[str, Any]) -> AssistantStreamEvent:
    return AssistantStreamEvent(
        sse_type="tool-output-available",
        payload={"toolCallId": call_id, "output": output},
    )


class TestToolStartedNarration:
    def test_real_tool_call_start_is_narrated_before_the_answer(self) -> None:
        """MUTATION PROOF: removing this narration means total silence
        during a real multi-step tool call instead of the required
        "I'll check X" milestone.
        """
        events = [_tool_start("c1", "getPipelineHealth")]
        display, tts = _drive(events)

        assert any("pipeline" in d.lower() for d in display)
        assert any("pipeline" in c.lower() for c in tts)

    def test_same_tool_called_twice_is_narrated_only_once(self) -> None:
        """MUTATION PROOF: without dedupe, a turn with N calls to the same
        tool repeats "Let me check X" N times — chatty, not concise (Phase 4).
        """
        events = [
            _tool_start("c1", "getPipelineHealth"),
            _tool_output("c1", {"results": [1, 2]}),
            _tool_start("c2", "getPipelineHealth"),
        ]
        _, tts = _drive(events)

        started_count = sum(1 for c in tts if "let me check" in c.lower())
        assert started_count == 1

    def test_unknown_tool_name_still_gets_a_generic_honest_phrase(self) -> None:
        events = [_tool_start("c1", "someCustomVendorSyncTool")]
        _, tts = _drive(events)
        assert any("custom vendor sync" in c.lower() for c in tts)


class TestToolCompletedNarration:
    def test_real_result_count_is_narrated(self) -> None:
        events = [
            _tool_start("c1", "listOpportunities"),
            _tool_output("c1", {"results": [{"name": "Acme"}] * 11, "totalResults": 11}),
        ]
        _, tts = _drive(events)

        assert any("found 11" in c.lower() for c in tts)

    def test_empty_result_list_is_not_narrated_as_a_fake_finding(self) -> None:
        """MUTATION PROOF: narrating "Found 0" as if it were a genuine
        finding worth announcing would be filler, not honest milestone
        narration — silence is correct here.
        """
        events = [
            _tool_start("c1", "listOpportunities"),
            _tool_output("c1", {"results": []}),
        ]
        _, tts = _drive(events)

        assert not any("found 0" in c.lower() for c in tts)

    def test_real_tool_failure_is_narrated_honestly_not_a_false_success(self) -> None:
        events = [
            _tool_start("c1", "updateDealStage"),
            _tool_output(
                "c1",
                {"success": False, "error": "Salesforce rejected the field update"},
            ),
        ]
        _, tts = _drive(events)

        full = " ".join(tts).lower()
        assert "didn't go through" in full
        assert "salesforce rejected the field update" in full

    def test_opaque_output_with_no_sayable_shape_stays_silent(self) -> None:
        """Non-list, non-count, non-error payloads must not produce an
        invented sentence disconnected from real structured data.
        """
        events = [
            _tool_start("c1", "getConnectorStatus"),
            _tool_output("c1", {"status": "connected"}),
        ]
        _, tts = _drive(events)

        # Only the tool-started narration should be present, nothing extra.
        assert len(tts) == 1

    def test_output_for_unknown_call_id_never_crashes_the_turn(self) -> None:
        """A tool-output-available with no matching tool-input-available in
        this turn (defensive edge case; live traffic always pairs them) must
        never raise — real output data can still be narrated with an empty
        tool-name label rather than blowing up the turn.
        """
        events = [_tool_output("unknown-call", {"results": [1]})]
        display, tts = _drive(events)  # must not raise
        # Word-boundary regression fix (2026-09-06): every independently-
        # pushed spoken segment now carries a trailing space so consecutive
        # TTS frames are never glued together with no separator (see
        # `_push_spoken_text`) — assert the exact fixed value, not a substring.
        assert tts == ["Found 1. "]


class TestPhase3HonestWriteStateSpeechEndToEnd:
    def test_write_call_speaks_executing_then_confirmed_with_real_detail(self) -> None:
        events = [
            _tool_start("c1", "moveDealStage"),
            _tool_output("c1", {"success": True, "stage": "Negotiation"}),
        ]
        _, tts = _drive(events)

        # Trailing space per segment is the word-boundary regression fix
        # (2026-09-06) — see `_push_spoken_text`.
        assert tts == ["I'm moving that now. ", "Done — I moved it to Negotiation. "]

    def test_write_call_confirmed_never_precedes_the_real_output_event(self) -> None:
        """MUTATION PROOF (HARD CONSTRAINT): reordering these two events must
        change what gets said — CONFIRMED text must only ever be produced
        once tool-output-available has actually arrived, never at
        tool-input-available time.
        """
        started_only = [_tool_start("c1", "moveDealStage")]
        _, tts_started_only = _drive(started_only)
        assert tts_started_only == ["I'm moving that now. "]
        assert not any("done" in c.lower() for c in tts_started_only)

    def test_write_call_failure_speaks_the_real_rejection_reason(self) -> None:
        events = [
            _tool_start("c1", "updateDealStage"),
            _tool_output(
                "c1",
                {"success": False, "error": "Salesforce rejected: stage is locked"},
            ),
        ]
        _, tts = _drive(events)

        assert tts == [
            "I'm updating that now. ",
            "That didn't go through — Salesforce rejected: stage is locked. ",
        ]
        assert not any("done" in c.lower() for c in tts)


class TestNarrationDoesNotCorruptTheFinalAnswer:
    def test_narration_and_final_text_delta_both_reach_tts_in_order(self) -> None:
        events = [
            _tool_start("c1", "getPipelineHealth"),
            _tool_output("c1", {"results": [1, 2, 3]}),
            AssistantStreamEvent(sse_type="text-delta", payload={"delta": "You have three open deals."}),
        ]
        _, tts = _drive(events)

        joined = " ".join(tts).lower()
        assert "let me check" in joined
        assert "found 3" in joined
        assert "three open deals" in joined
        # Narration must precede the final answer, matching real execution order.
        assert tts.index(next(c for c in tts if "let me check" in c.lower())) < tts.index(
            next(c for c in tts if "three open deals" in c.lower())
        )
