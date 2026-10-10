"""A backchannel final ("yeah" over the bot) is relayed marked, so the client keeps the reply.

Before: the relay mirrored every final as a plain transcript; the browser then
reset the visible reply and fired onUserFinal, adding a user message nobody sent
and wiping the reply the bot was still speaking.
"""
from __future__ import annotations

import pytest
from pipecat.frames.frames import Frame, OutputTransportMessageUrgentFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.services.pipecat_voice.transcript_relay import (
    TranscriptRelayProcessor,
    classify_non_turn_final,
)
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession


async def _relay(text: str, session: VoicePipelineSession | None) -> dict:
    relay = TranscriptRelayProcessor(voice_session=session)
    await BaseObject.setup(relay, TaskManager())
    pushed: list[Frame] = []

    async def _capture(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        pushed.append(frame)

    relay.push_frame = _capture  # type: ignore[method-assign]
    await relay.process_frame(
        TranscriptionFrame(user_id="u", text=text, timestamp="t"), FrameDirection.DOWNSTREAM
    )
    return next(
        f.message
        for f in pushed
        if isinstance(f, OutputTransportMessageUrgentFrame) and f.message.get("type") == "transcript"
    )


def _speaking_session() -> VoicePipelineSession:
    session = VoicePipelineSession()
    session.bot_speaking = True  # set by the interrupt reporter from Bot*SpeakingFrame
    return session


@pytest.mark.asyncio
async def test_backchannel_over_bot_speech_is_marked():
    msg = await _relay("yeah", _speaking_session())
    assert msg["final"] is True
    assert msg["backchannel"] is True
    assert msg["turn_taking"] == "backchannel"


@pytest.mark.asyncio
async def test_real_interruption_over_bot_speech_is_not_marked():
    msg = await _relay("wait, what about churn last month?", _speaking_session())
    assert "backchannel" not in msg


@pytest.mark.asyncio
async def test_yes_after_a_bot_question_is_an_answer_not_a_backchannel():
    session = _speaking_session()
    session.answer_expected = lambda: True
    msg = await _relay("yeah", session)
    assert "backchannel" not in msg


@pytest.mark.asyncio
async def test_bot_echo_is_marked():
    session = _speaking_session()
    session.note_bot_speech("Revenue was up twelve percent this quarter")
    msg = await _relay("revenue was up twelve percent this quarter", session)
    assert msg["turn_taking"] == "echo"


@pytest.mark.asyncio
async def test_presence_check_while_thinking_is_marked_held():
    session = VoicePipelineSession()
    session.assistant_generating = True
    msg = await _relay("you there?", session)
    assert msg["turn_taking"] == "thinking_hold"


@pytest.mark.asyncio
async def test_idle_bot_or_no_session_never_marks():
    assert "backchannel" not in await _relay("yeah", VoicePipelineSession())
    assert "backchannel" not in await _relay("yeah", None)


@pytest.mark.asyncio
async def test_interrupt_reporter_publishes_bot_speaking_on_the_session():
    from pipecat.frames.frames import BotStartedSpeakingFrame, BotStoppedSpeakingFrame

    from app.services.pipecat_voice.interrupt_reporter import ElevenLabsInterruptReporter

    session = VoicePipelineSession()
    reporter = ElevenLabsInterruptReporter(voice_session=session)
    await BaseObject.setup(reporter, TaskManager())

    async def _noop(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        return None

    reporter.push_frame = _noop  # type: ignore[method-assign]
    await reporter.process_frame(BotStartedSpeakingFrame(), FrameDirection.UPSTREAM)
    assert session.bot_speaking is True
    await reporter.process_frame(BotStoppedSpeakingFrame(), FrameDirection.UPSTREAM)
    assert session.bot_speaking is False


def test_classifier_survives_a_broken_session():
    class _Broken:
        bot_speaking = True

        def is_echo_of_bot(self, _text: str) -> bool:
            raise RuntimeError("boom")

    assert classify_non_turn_final("yeah", _Broken()) is None
