"""Round-count audit (2026-09-06): per-tool latency instrumentation.

Addendum 3 to docs/delivery/voice-slo-parallelism-standard-2026-09-05.md found
`consequential_write_shaped` voice turns spend 3.2-3.7s of real wall-clock time
per round in "tool-execution latency between LLM calls" but could only
attribute that to *some* round, not a specific tool -- the existing
`pipecat_voice_turn_latency` log line only fires at LLM-call boundaries
(`data-intelligence` events).

This closes that attribution gap: `GravitreCognitiveLLMService._run_gravitre_turn`
now logs `pipecat_voice_tool_latency` with the real elapsed wall-clock time
between a specific tool's `tool-input-available` and its matching
`tool-output-available` event, keyed by `toolCallId` (mirrors the existing
`tool_names_by_call_id` pairing already used for honest narration).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from unittest.mock import AsyncMock, patch

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService


def _drive_with_logs(events_and_delays: list[tuple[Any, float]], caplog: Any) -> list[str]:
    """Run one turn against a scripted, real-time-delayed event sequence;
    return every `pipecat_voice_tool_latency` log message emitted.
    """

    async def _fake_stream(**_kwargs: Any):
        for event, delay in events_and_delays:
            if delay:
                await asyncio.sleep(delay)
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
    service.push_frame = AsyncMock()
    service._push_llm_text = AsyncMock()
    service.start_ttfb_metrics = AsyncMock()
    service.stop_ttfb_metrics = AsyncMock()

    class _FakeContext:
        def get_messages(self) -> list[dict[str, Any]]:
            return [{"role": "user", "content": "update the deal"}]

    with patch(
        "app.operators.agent_intelligence.get_agent_intelligence",
        return_value=fake_intelligence,
    ):
        with caplog.at_level(logging.INFO, logger="app.services.pipecat_voice.cognitive_llm"):
            asyncio.run(service._run_gravitre_turn(_FakeContext()))

    return [r.getMessage() for r in caplog.records]


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


class TestPerToolLatencyLogging:
    def test_real_elapsed_time_between_input_and_output_is_logged_by_tool_name(
        self, caplog: Any
    ) -> None:
        """MUTATION PROOF: remove the log call (or the started_at bookkeeping)
        and no `pipecat_voice_tool_latency` message appears at all — this is
        the exact gap Addendum 3 flagged (round-level attribution only, no
        per-tool identity).
        """
        events = [
            (_tool_start("c1", "updateDealStage"), 0.0),
            (_tool_output("c1", {"success": True}), 0.15),
        ]
        messages = _drive_with_logs(events, caplog)

        latency_lines = [m for m in messages if "pipecat_voice_tool_latency" in m]
        assert len(latency_lines) == 1
        line = latency_lines[0]
        assert "tool=updateDealStage" in line
        # Real measured delay was ~150ms; assert it's in the right ballpark,
        # not hardcoded/faked -- generous bounds for CI scheduling jitter.
        elapsed = int(line.split("elapsed_ms=")[1].split()[0])
        assert 100 <= elapsed <= 2000

    def test_multiple_tool_calls_are_each_logged_under_their_own_name(
        self, caplog: Any
    ) -> None:
        events = [
            (_tool_start("c1", "getPipelineHealth"), 0.0),
            (_tool_output("c1", {"results": [1]}), 0.05),
            (_tool_start("c2", "updateDealStage"), 0.0),
            (_tool_output("c2", {"success": True}), 0.05),
        ]
        messages = _drive_with_logs(events, caplog)
        latency_lines = [m for m in messages if "pipecat_voice_tool_latency" in m]

        assert len(latency_lines) == 2
        assert any("tool=getPipelineHealth" in m for m in latency_lines)
        assert any("tool=updateDealStage" in m for m in latency_lines)

    def test_output_for_unknown_call_id_does_not_log_a_latency_line(
        self, caplog: Any
    ) -> None:
        """No matching tool-input-available means no real started_at to
        measure from -- must stay silent rather than log a fabricated 0ms.
        """
        events = [(_tool_output("unknown-call", {"results": [1]}), 0.0)]
        messages = _drive_with_logs(events, caplog)

        assert not any("pipecat_voice_tool_latency" in m for m in messages)

    def test_since_turn_start_ms_is_also_present_for_round_correlation(
        self, caplog: Any
    ) -> None:
        """Needed to correlate a specific tool's latency back to which of the
        6 chained rounds (Addendum 3) it belongs to.
        """
        events = [
            (_tool_start("c1", "updateDealStage"), 0.02),
            (_tool_output("c1", {"success": True}), 0.02),
        ]
        messages = _drive_with_logs(events, caplog)
        line = next(m for m in messages if "pipecat_voice_tool_latency" in m)
        assert "since_turn_start_ms=" in line
