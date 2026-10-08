"""A narration sentence is synthesized when it is pushed, not with the answer.

Pipecat's TTS sentence aggregator releases a sentence only once it sees the
first character of the next one. A milestone narration pushed while the brain
works was therefore held until the answer's first token and spoken with it.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import (
    AggregatedTextFrame,
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.tts_service import TTSService
from pipecat.tests.utils import SleepFrame, run_test

from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService

NARRATION = "Checking your accounts now."
ANSWER = "Acme is the priority account."


class _RecordingTTS(TTSService):
    def __init__(self, log: list[tuple[str, str]]) -> None:
        super().__init__(sample_rate=24000)
        self._log = log

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        if isinstance(frame, LLMTextFrame) and not frame.skip_tts:
            self._log.append(("text_in", frame.text.strip()))
        await super().process_frame(frame, direction)

    async def run_tts(self, text: str, context_id: str):
        self._log.append(("synthesize", text.strip()))
        yield None


async def _bridge_frames(*, answer_pending: bool) -> list[Frame]:
    service = GravitreCognitiveLLMService(
        app_settings=object(),
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
    )
    pushed: list[Frame] = []

    async def _push(frame: Any, *_a: Any, **_k: Any) -> None:
        pushed.append(frame)

    async def _push_llm_text(text: str) -> None:
        pushed.append(LLMTextFrame(text))

    service.push_frame = AsyncMock(side_effect=_push)
    service._push_llm_text = AsyncMock(side_effect=_push_llm_text)
    service._tts_text_pending = answer_pending
    await service._speak_narration(NARRATION)
    return [f for f in pushed if isinstance(f, (LLMTextFrame, AggregatedTextFrame))]


async def _run(narration_frames: list[Frame]) -> list[tuple[str, str]]:
    log: list[tuple[str, str]] = []
    await run_test(
        _RecordingTTS(log),
        frames_to_send=[
            LLMFullResponseStartFrame(),
            *narration_frames,
            SleepFrame(sleep=0.2),  # the brain is still working
            LLMTextFrame(ANSWER + " "),
            LLMFullResponseEndFrame(),
        ],
    )
    return log


@pytest.mark.asyncio
async def test_narration_is_synthesized_before_the_answer_arrives() -> None:
    log = await _run(await _bridge_frames(answer_pending=False))
    assert log.index(("synthesize", NARRATION)) < log.index(("text_in", ANSWER))
    assert ("synthesize", ANSWER) in log
    assert [e for e in log if e[0] == "synthesize"].count(("synthesize", NARRATION)) == 1


@pytest.mark.asyncio
async def test_a_plain_text_narration_waits_for_the_next_text() -> None:
    # The previous behavior, kept for when answer text may still sit in the
    # aggregator: order is preserved, at the cost of the hold.
    frames = await _bridge_frames(answer_pending=True)
    assert all(isinstance(f, LLMTextFrame) for f in frames)
    log = await _run(frames)
    assert log.index(("synthesize", NARRATION)) > log.index(("text_in", ANSWER))


@pytest.mark.asyncio
async def test_narration_draft_still_reaches_the_reporter_but_not_tts_or_context() -> None:
    frames = await _bridge_frames(answer_pending=False)
    draft = [f for f in frames if type(f) is LLMTextFrame]
    assert len(draft) == 1 and draft[0].text == NARRATION + " "
    assert draft[0].skip_tts is True and draft[0].append_to_context is False
