"""Does the client ever receive a final user transcript on the Pipecat path?

Measured in production 2026-09-08: four live turns received zero
``{"type": "transcript"}`` messages, because ``LLMUserAggregator`` consumes
``TranscriptionFrame`` before ``transport.output()`` and the serializer therefore
never sees one. ``TranscriptRelayProcessor`` mirrors finals as a message frame,
which the aggregator passes through untouched.

Same harness pattern as the sibling interrupt-reporter tests: a real TaskManager
plus a captured ``push_frame`` rather than standing up a full pipeline.
"""
from __future__ import annotations

import pytest
from pipecat.frames.frames import (
    Frame,
    InterimTranscriptionFrame,
    OutputTransportMessageUrgentFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.base_object import BaseObject
from pipecat.utils.asyncio.task_manager import TaskManager

from app.services.pipecat_voice.json_audio_serializer import GravitreJsonAudioSerializer
from app.services.pipecat_voice.transcript_relay import TranscriptRelayProcessor


async def _drive(
    frames: list[tuple[Frame, FrameDirection]],
) -> tuple[list[Frame], TranscriptRelayProcessor]:
    relay = TranscriptRelayProcessor()
    await BaseObject.setup(relay, TaskManager())

    pushed: list[Frame] = []

    async def _capture(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM):
        pushed.append(frame)

    relay.push_frame = _capture  # type: ignore[method-assign]

    for frame, direction in frames:
        await relay.process_frame(frame, direction)
    return pushed, relay


def _transcript_messages(pushed: list[Frame]) -> list[dict]:
    return [
        f.message
        for f in pushed
        if isinstance(f, OutputTransportMessageUrgentFrame)
        and isinstance(f.message, dict)
        and f.message.get("type") == "transcript"
    ]


@pytest.mark.asyncio
async def test_final_transcription_is_mirrored_to_client():
    frame = TranscriptionFrame(user_id="u1", text="Did the HubSpot sync finish", timestamp="t")
    pushed, relay = await _drive([(frame, FrameDirection.DOWNSTREAM)])

    msgs = _transcript_messages(pushed)
    assert len(msgs) == 1
    assert msgs[0] == {
        "type": "transcript",
        "text": "Did the HubSpot sync finish",
        "final": True,
        "user_id": "u1",
    }
    assert relay.relayed_count == 1


@pytest.mark.asyncio
async def test_original_frame_still_passes_through():
    """The aggregator downstream must still receive the transcription itself."""
    frame = TranscriptionFrame(user_id="u1", text="hello", timestamp="t")
    pushed, _ = await _drive([(frame, FrameDirection.DOWNSTREAM)])

    assert any(f is frame for f in pushed), "original TranscriptionFrame was swallowed"
    # Pass-through happens before the mirror, so the LLM turn is never delayed
    # behind an extra client message.
    assert pushed.index(frame) == 0


@pytest.mark.asyncio
async def test_interim_transcription_is_not_relayed():
    """Interim relay would activate the hook's client-side bargeIn() path.

    Server-side Flux barge-in already covers interruption, so mirroring interims
    would add a second interrupt trigger — deliberately out of scope.
    """
    interim = InterimTranscriptionFrame(user_id="u1", text="did the hub", timestamp="t")
    pushed, relay = await _drive([(interim, FrameDirection.DOWNSTREAM)])

    assert _transcript_messages(pushed) == []
    assert relay.relayed_count == 0
    assert any(f is interim for f in pushed), "interim frame must still pass through"


@pytest.mark.asyncio
async def test_upstream_direction_is_not_relayed():
    frame = TranscriptionFrame(user_id="u1", text="hello", timestamp="t")
    pushed, relay = await _drive([(frame, FrameDirection.UPSTREAM)])

    assert _transcript_messages(pushed) == []
    assert relay.relayed_count == 0


@pytest.mark.asyncio
async def test_empty_transcription_is_not_relayed():
    frame = TranscriptionFrame(user_id="u1", text="   ", timestamp="t")
    pushed, relay = await _drive([(frame, FrameDirection.DOWNSTREAM)])

    assert _transcript_messages(pushed) == []
    assert relay.relayed_count == 0


@pytest.mark.asyncio
async def test_relayed_message_serializes_to_the_shape_the_frontend_expects():
    """End-to-end shape check: the hook keys on type=="transcript" and msg.final."""
    frame = TranscriptionFrame(user_id="u1", text="status", timestamp="t")
    pushed, _ = await _drive([(frame, FrameDirection.DOWNSTREAM)])
    message_frame = next(
        f for f in pushed if isinstance(f, OutputTransportMessageUrgentFrame)
    )

    wire = await GravitreJsonAudioSerializer().serialize(message_frame)

    import json

    decoded = json.loads(wire)
    assert decoded["type"] == "transcript"
    assert decoded["final"] is True
    assert decoded["text"] == "status"


@pytest.mark.asyncio
async def test_relay_is_wired_into_the_live_pipeline_before_the_aggregator():
    """A relay that exists but is not installed upstream of user_agg fixes nothing."""
    import inspect

    from app.services.pipecat_voice import pipeline as pipeline_module

    source = inspect.getsource(pipeline_module.build_pipecat_voice_task)
    assert "TranscriptRelayProcessor()" in source
    # Scope to the Pipeline([...]) list: "user_agg," also appears earlier at the
    # LLMContextAggregatorPair assignment, which would make the order check pass
    # for the wrong reason.
    listing = source[source.index("pipeline = Pipeline(") :]
    assert listing.index("TranscriptRelayProcessor()") < listing.index("user_agg,")
    assert listing.index("stt,") < listing.index("TranscriptRelayProcessor()")
