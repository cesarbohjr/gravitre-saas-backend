"""Regression: independently-pushed spoken segments must never be glued
together with no separating whitespace once Pipecat's own TTS text
aggregator concatenates them.

Live user report (2026-09-06): "voice reverted to sounding robotic" on the
same deploy as the llm_first_token optimization pass. Root-cause trace (this
program's own Phase 0 reconciliation) ruled out every code change in that
pass (context-size-breakdown instrumentation, prefetch backgrounding,
per-tool latency logging — all reviewed diff-by-diff, none touch TTS
voice/model selection or response-text generation) and instead found a real,
pre-existing, concrete defect: a live Railway log pull during the
investigation showed ElevenLabsTTSService's actual "Generating TTS" payload
for a real `consequential_write_shaped` turn read:

    "...knowledge base.Found 3.I can't send that email from the information
    provided.I don't have Sarah's email address..."

Every sentence/narration boundary was glued to the next word with *zero*
whitespace. Root cause: `_sanitize_for_tts` (via
`strip_and_validate_delivery_tags`) unconditionally `.strip()`s every chunk
it returns, and `GravitreCognitiveLLMService` calls `_push_llm_text` once per
narration sentence AND once per speakable answer chunk — each becomes its
own `LLMTextFrame`. Pipecat's `SimpleTextAggregator` (pipecat/utils/text/
simple_text_aggregator.py) appends the raw characters of every incoming
`TextFrame` to one running buffer with no separator inserted between frames.
Two adjacent, independently-pushed, whitespace-stripped segments therefore
reach ElevenLabs Flash v2.5 as one run-on string — exactly the "robotic"/
garbled cadence reported live.

Fix: `_push_spoken_text` (see cognitive_llm.py) appends exactly one trailing
space to every segment it pushes, so two adjacent frames always have a real
word-boundary space between them once concatenated — matching what Pipecat's
own aggregator will actually do with them.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any
from unittest.mock import AsyncMock, patch

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService

# Matches the exact defect class: sentence-ending punctuation directly
# followed by a letter/digit with no whitespace between them, e.g.
# "base.Found" or "provided.I" or "3.I".
_GLUED_BOUNDARY = re.compile(r"[.!?][A-Za-z0-9]")


def _drive(events: list[Any]) -> list[str]:
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

    tts_chunks: list[str] = []

    async def _capture_push_llm_text(text: str) -> None:
        tts_chunks.append(text)

    service.push_frame = AsyncMock()
    service._push_llm_text = AsyncMock(side_effect=_capture_push_llm_text)
    service.start_ttfb_metrics = AsyncMock()
    service.stop_ttfb_metrics = AsyncMock()

    class _FakeContext:
        def get_messages(self) -> list[dict[str, Any]]:
            return [{"role": "user", "content": "check the knowledge base and email Sarah"}]

    with patch(
        "app.operators.agent_intelligence.get_agent_intelligence",
        return_value=fake_intelligence,
    ):
        asyncio.run(service._run_gravitre_turn(_FakeContext()))

    return tts_chunks


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


class TestTtsWordBoundaryRegression:
    def test_narration_and_final_answer_never_glue_together_when_concatenated(
        self,
    ) -> None:
        """MUTATION PROOF: revert `_push_spoken_text` to push the bare,
        already-stripped `spoken` text (the pre-fix behavior) and this test
        fails — `"".join(tts_chunks)` reproduces the exact live defect
        ("knowledge base.Found 3.I can't send...").

        This simulates exactly what Pipecat's `SimpleTextAggregator` does to
        real, independently-pushed `LLMTextFrame`s: concatenate their raw
        characters with no separator. If our own segments do not already
        carry the separating space, the aggregator cannot invent one.
        """
        events = [
            _tool_start("c1", "searchKnowledgeBase"),
            _tool_output("c1", {"results": [1, 2, 3], "totalResults": 3}),
            AssistantStreamEvent(
                sse_type="text-delta",
                payload={"delta": "I can't send that email from the information provided."},
            ),
        ]
        tts_chunks = _drive(events)

        assert len(tts_chunks) >= 2, "need at least narration + answer to exercise the boundary"
        glued_as_the_real_aggregator_would_see_it = "".join(tts_chunks)
        found = _GLUED_BOUNDARY.findall(glued_as_the_real_aggregator_would_see_it)
        assert not found, (
            "sentence boundary glued with no space when concatenated exactly "
            f"as Pipecat's own aggregator would: {glued_as_the_real_aggregator_would_see_it!r}"
        )

    def test_two_consecutive_narration_sentences_never_glue_together(self) -> None:
        """The exact `"...Found 3.I can't send"` pattern from the live log
        came from tool-STARTED narration immediately followed by
        tool-COMPLETED narration with no intervening answer text — cover
        that boundary directly, independent of any final-answer text.
        """
        events = [
            _tool_start("c1", "searchKnowledgeBase"),
            _tool_output("c1", {"results": [1, 2, 3], "totalResults": 3}),
        ]
        tts_chunks = _drive(events)

        assert len(tts_chunks) >= 1
        glued = "".join(tts_chunks)
        assert not _GLUED_BOUNDARY.findall(glued), (
            f"narration segments glued together with no space: {glued!r}"
        )

    def test_every_independently_pushed_segment_carries_a_trailing_space(self) -> None:
        """Direct assertion on the fix mechanism itself: every non-empty
        chunk actually pushed to TTS must end in a single trailing space,
        so any two adjacent pushes are guaranteed a real word-boundary
        separator once Pipecat's aggregator concatenates them.
        """
        events = [
            _tool_start("c1", "searchKnowledgeBase"),
            _tool_output("c1", {"results": [1, 2, 3], "totalResults": 3}),
        ]
        tts_chunks = _drive(events)

        assert tts_chunks, "expected at least one narration chunk"
        for chunk in tts_chunks:
            assert chunk.endswith(" "), f"chunk missing trailing separator space: {chunk!r}"
            assert not chunk.endswith("  "), f"chunk has a double space, not a single one: {chunk!r}"
