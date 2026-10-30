"""Pinned SDK protocol reaches the real strategy before committed EOT.

Only the pipeline I/O boundary is replaced; Flux message dispatch, frame types,
strategy timers/classification, and final transcription use their real code.
"""
import asyncio
from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import (
    BotStartedSpeakingFrame, InterimTranscriptionFrame, TranscriptionFrame,
)

from app.services.pipecat_voice.flux_stt import InterimAwareFluxSTTService
from tests.services.pipecat_voice.test_backchannel_turn_strategy import _make_strategy


async def connected_strategy():
    strategy, recorder = await _make_strategy(grace_period_s=5)
    await strategy.process_frame(BotStartedSpeakingFrame())
    service = InterimAwareFluxSTTService(api_key='offline-test-only', model='flux-general-en')
    emitted = []

    async def broadcast(frame_cls, **kwargs):
        await strategy.process_frame(frame_cls(**kwargs))

    async def output(frame, *args, **kwargs):
        emitted.append(frame)
        await strategy.process_frame(frame)

    service.broadcast_frame = AsyncMock(side_effect=broadcast)
    service.push_frame = AsyncMock(side_effect=output)
    return service, strategy, recorder, emitted


@pytest.mark.asyncio
@pytest.mark.parametrize('event', ['StartOfTurn', 'Update'])
async def test_cancel_reaches_classifier_before_end_of_turn(event):
    service, strategy, recorder, emitted = await connected_strategy()
    try:
        if event == 'Update':
            await service._handle_turn_info({'event': 'StartOfTurn', 'transcript': ''})
            assert not recorder.turn_started_calls
        await service._handle_turn_info({'event': event, 'transcript': 'cancel it'})
        await asyncio.sleep(0)
        assert len(recorder.turn_started_calls) == 1
        assert recorder.turn_started_calls[0].enable_interruptions is True
        assert [f.text for f in emitted if isinstance(f, InterimTranscriptionFrame)] == ['cancel it']
        assert not any(isinstance(f, TranscriptionFrame) for f in emitted)
    finally:
        await strategy.cleanup()
        await service.cleanup()


@pytest.mark.asyncio
async def test_backchannel_partial_does_not_interrupt_and_final_is_still_sdk_owned():
    service, strategy, recorder, emitted = await connected_strategy()
    try:
        await service._handle_turn_info({'event': 'StartOfTurn', 'transcript': 'uh-huh'})
        await service._handle_turn_info({'event': 'Update', 'transcript': 'uh-huh'})
        assert not recorder.turn_started_calls
        assert not any(isinstance(f, TranscriptionFrame) for f in emitted)
        await service._handle_turn_info({'event': 'EndOfTurn', 'transcript': 'uh-huh'})
        await asyncio.sleep(0)
        assert len(recorder.turn_started_calls) == 1
        assert recorder.turn_started_calls[0].enable_interruptions is False
        assert len([f for f in emitted if isinstance(f, TranscriptionFrame)]) == 1
        count = len(emitted)
        await service._handle_turn_info({'event': 'Update', 'transcript': 'cancel it'})
        assert len(emitted) == count  # no stale partial after committed EOT
    finally:
        await strategy.cleanup()
        await service.cleanup()


@pytest.mark.asyncio
async def test_partial_approval_never_becomes_a_final_transcript():
    service, strategy, recorder, emitted = await connected_strategy()
    try:
        await service._handle_turn_info({'event': 'StartOfTurn', 'transcript': 'yes'})
        await service._handle_turn_info({'event': 'Update', 'transcript': 'yes wait hold on'})
        assert emitted and all(isinstance(f, InterimTranscriptionFrame) for f in emitted)
        await service._handle_turn_info({'event': 'EndOfTurn', 'transcript': 'yes wait hold on'})
        finals = [f for f in emitted if isinstance(f, TranscriptionFrame)]
        assert len(finals) == 1 and finals[0].text == 'yes wait hold on'
    finally:
        await strategy.cleanup()
        await service.cleanup()
