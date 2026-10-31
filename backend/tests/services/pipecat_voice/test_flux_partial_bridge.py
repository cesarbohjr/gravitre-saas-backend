"""Pinned SDK protocol reaches the real strategy before committed EOT.

Only the pipeline I/O boundary is replaced; Flux message dispatch, frame types,
strategy timers/classification, and final transcription use their real code.
"""
import asyncio
from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import (
    BotStartedSpeakingFrame, InterimTranscriptionFrame, TranscriptionFrame,
    ProposedUserStartedSpeakingFrame,
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
        assert all(f.gravitre_turn_control_only for f in emitted if isinstance(f, InterimTranscriptionFrame))
        assert not any(isinstance(f, TranscriptionFrame) for f in emitted)
    finally:
        await strategy.cleanup()
        await service.cleanup()


@pytest.mark.asyncio
async def test_normal_listening_retains_sdk_final_without_new_interim_work():
    service, strategy, recorder, emitted = await connected_strategy()
    service.partial_control_enabled = lambda: False
    try:
        await service._handle_turn_info({'event': 'StartOfTurn', 'transcript': 'ordinary question'})
        await service._handle_turn_info({'event': 'Update', 'transcript': 'ordinary question updated'})
        assert not emitted
        await service._handle_turn_info({'event': 'EndOfTurn', 'transcript': 'ordinary question updated'})
        assert len([f for f in emitted if isinstance(f, TranscriptionFrame)]) == 1
        assert not any(isinstance(f, InterimTranscriptionFrame) for f in emitted)
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


@pytest.mark.asyncio
async def test_indexed_cancel_update_precedes_native_start_without_duplicate_turn():
    service, strategy, recorder, emitted = await connected_strategy()
    try:
        await service._handle_turn_info(dict(event='Update', turn_index=0, transcript='can'))
        assert not recorder.turn_started_calls and not emitted
        await service._handle_turn_info(dict(event='Update', turn_index=0, transcript='cancel'))
        assert len(recorder.turn_started_calls) == 1
        assert recorder.turn_started_calls[0].enable_interruptions is True
        assert not service._user_is_speaking  # native SDK state is still native
        await service._handle_turn_info(dict(event='Update', turn_index=0, transcript='cancel it'))
        await service._handle_turn_info(dict(event='StartOfTurn', turn_index=0, transcript='cancel it'))
        assert service._user_is_speaking
        assert service.broadcast_frame.await_count == 1
        assert len(recorder.turn_started_calls) == 1
        assert all(isinstance(f, InterimTranscriptionFrame) for f in emitted)
        await service._handle_turn_info(dict(event='EndOfTurn', turn_index=0, transcript='Cancel it.'))
        assert len([f for f in emitted if isinstance(f, TranscriptionFrame)]) == 1
        count = len(emitted)
        for index in (0, None, -1, True):
            await service._handle_turn_info(dict(event='Update', turn_index=index, transcript='cancel'))
        assert len(emitted) == count  # stale/ambiguous generation cannot rearm
        await service._handle_turn_info(dict(event='Update', turn_index=1, transcript='cancel'))
        assert len(emitted) > count  # fresh provider turn can still cancel
    finally:
        await strategy.cleanup()
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize('text', ['yes', 'uh-huh', 'can', 'stop', 'stop talking keep working', '', 'do not cancel'])
async def test_pre_start_updates_do_not_promote_approval_backchannel_or_speech_only_stop(text):
    service, strategy, recorder, emitted = await connected_strategy()
    try:
        await service._handle_turn_info(dict(event='Update', turn_index=0, transcript=text))
        assert not emitted and not recorder.turn_started_calls
        service.broadcast_frame.assert_not_awaited()
    finally:
        await strategy.cleanup()
        await service.cleanup()


@pytest.mark.asyncio
async def test_early_cancel_disabled_outside_active_work_or_speech():
    service, strategy, recorder, emitted = await connected_strategy()
    service.partial_control_enabled = lambda: False
    try:
        await service._handle_turn_info(dict(event='Update', turn_index=0, transcript='cancel'))
        assert not emitted and not recorder.turn_started_calls
        service.broadcast_frame.assert_not_awaited()
    finally:
        await strategy.cleanup()
        await service.cleanup()


@pytest.mark.asyncio
async def test_reconnect_allows_provider_to_restart_turn_indices():
    from unittest.mock import patch
    from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService

    service, strategy, recorder, emitted = await connected_strategy()
    try:
        await service._handle_turn_info(dict(event='StartOfTurn', turn_index=0, transcript='uh-huh'))
        await service._handle_turn_info(dict(event='EndOfTurn', turn_index=0, transcript='uh-huh'))
        count = len(emitted)
        await service._handle_turn_info(dict(event='Update', turn_index=0, transcript='cancel'))
        assert len(emitted) == count
        # Replace connection I/O only; exercise adapter state and SDK dispatch.
        with patch.object(DeepgramFluxSTTService, '_connect', new_callable=AsyncMock):
            await service._connect()
        await service._handle_turn_info(dict(event='Update', turn_index=0, transcript='cancel'))
        assert len(emitted) > count
        assert recorder.turn_started_calls[-1].enable_interruptions is True
    finally:
        await strategy.cleanup()
        await service.cleanup()
