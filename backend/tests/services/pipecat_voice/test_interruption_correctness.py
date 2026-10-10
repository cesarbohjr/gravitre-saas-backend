"""Barge-in correctness: the write stop goes first, and audio keeps its own reply id.

1. The conversation stop that blocks write commits is armed before anything
   is awaited at a barge-in, so a slow ElevenLabs context cancel (or a slow
   Redis write) no longer leaves a window in which a write can commit.
2. Outbound audio is stamped with the reply that generated it, bound at
   generation time through the TTS context, not read from the session's
   current reply id when the frame is sent.
3. Audio of a cancelled reply is dropped server side; whatever does reach the
   serializer after the cut-off can only carry the old id.
"""
from __future__ import annotations

import asyncio
import json
import threading
from types import SimpleNamespace
from typing import Any

import pytest
from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMFullResponseStartFrame,
    OutputAudioRawFrame,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.services import chat_turn_cancel_service
from app.services.pipecat_voice.interrupt_reporter import ElevenLabsInterruptReporter
from app.services.pipecat_voice.json_audio_serializer import (
    REPLY_AUDIO_MARK,
    GravitreJsonAudioSerializer,
    ReplyAudioStampProcessor,
)
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession
from app.services.react_write_gate import WRITE_COMMIT_INTERRUPTED
from app.services.tool_types import ToolValidationError

ORG = "00000000-0000-4000-8000-0000000000a1"
USER = "00000000-0000-4000-8000-0000000000c3"
CONV = "00000000-0000-4000-8000-0000000000e5"
WRITE_ACTION = "email.send"


class _SlowTTS:
    """ElevenLabs stand-in whose context close does not return until released."""

    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.close_started = asyncio.Event()
        self.closed = False
        self._websocket = object()
        self._turn_context_id = "ctx-reply-1"

    def get_active_audio_context_id(self) -> str:
        return self._turn_context_id

    def get_audio_contexts(self) -> list[str]:
        return [self._turn_context_id]

    async def _close_context(self, _context_id: str) -> None:
        self.close_started.set()
        await self.release.wait()
        self.closed = True


class _SlowRedis:
    """Shared stop store whose write blocks until released (a slow Redis)."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.data: dict[str, str] = {}

    def setex(self, key: str, _ttl: int, value: str) -> None:
        self.release.wait(5)
        self.data[key] = value

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def delete(self, key: str) -> None:
        self.data.pop(key, None)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch):
    chat_turn_cancel_service.reset_local_stops_for_tests()
    # Audit rows are not what these tests are about.
    monkeypatch.setattr("app.services.pipecat_voice.voice_latency_metrics._write", lambda *a, **k: None)
    monkeypatch.setattr(
        "app.services.voice_barge_in_write.action_is_mutating_write",
        lambda action: action == WRITE_ACTION,
    )
    from app.services import voice_barge_in_write

    voice_barge_in_write.reset_write_effects_for_tests()
    yield
    chat_turn_cancel_service.reset_local_stops_for_tests()


async def _live_reporter(tts: Any, session: VoicePipelineSession) -> tuple[ElevenLabsInterruptReporter, list[Frame]]:
    reporter = ElevenLabsInterruptReporter(
        settings=SimpleNamespace(),
        org_id=ORG,
        user_id=USER,
        conversation_id=CONV,
        tts_service=tts,
        voice_session=session,
    )
    await BaseObject.setup(reporter, TaskManager())
    pushed: list[Frame] = []

    async def _capture(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        pushed.append(frame)

    reporter.push_frame = _capture  # type: ignore[method-assign]
    reporter.begin_turn("Email Sarah the deck")
    session.begin_reply()
    await reporter.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await reporter.process_frame(
        OutputTransportMessageUrgentFrame(message={"type": "assistant_text", "delta": "Sending it now."}),
        FrameDirection.DOWNSTREAM,
    )
    return reporter, pushed


def _write_ctx() -> SimpleNamespace:
    return SimpleNamespace(org_id=ORG, conversation_id=CONV, settings=None)


def _commit_is_refused() -> bool:
    from app.services.voice_barge_in_write import begin_write_effect

    try:
        begin_write_effect(_write_ctx(), WRITE_ACTION)
    except ToolValidationError as exc:
        assert exc.code == WRITE_COMMIT_INTERRUPTED
        return True
    return False


# --- 1. Barge-in race --------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("with_redis", [False, True], ids=["in_process_only", "slow_redis"])
async def test_write_commit_is_refused_while_the_tts_cancel_is_still_running(
    monkeypatch: pytest.MonkeyPatch, with_redis: bool
) -> None:
    redis = _SlowRedis() if with_redis else None
    monkeypatch.setattr(chat_turn_cancel_service, "get_redis_client", lambda _s=None: redis)
    tts = _SlowTTS()
    session = VoicePipelineSession()
    reporter, pushed = await _live_reporter(tts, session)

    # Before the barge-in the write would go through.
    assert _commit_is_refused() is False

    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
    # Let the detached bookkeeping start: the provider cancel is now stuck.
    await asyncio.wait_for(tts.close_started.wait(), 2)
    assert tts.closed is False
    assert isinstance(pushed[-1], InterruptionFrame)

    # The write commit attempted inside that window is refused.
    assert chat_turn_cancel_service.is_stop_requested(ORG, CONV) is True
    assert _commit_is_refused() is True
    if redis is not None:
        # And the shared (Redis) stop has not even been written yet.
        assert redis.data == {}

    tts.release.set()
    if redis is not None:
        redis.release.set()
    await reporter.settle_barge_in()
    assert tts.closed is True
    # The next confirmed turn releases the stop again.
    assert chat_turn_cancel_service.is_stop_requested(ORG, CONV) is False
    assert _commit_is_refused() is False


@pytest.mark.asyncio
async def test_stop_is_armed_before_the_interruption_leaves_the_reporter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_turn_cancel_service, "get_redis_client", lambda _s=None: None)
    session = VoicePipelineSession()
    reporter, pushed = await _live_reporter(_SlowTTS(), session)
    armed_when_pushed: list[bool] = []

    async def _capture(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        if isinstance(frame, (InterruptionFrame, OutputTransportMessageUrgentFrame)):
            armed_when_pushed.append(chat_turn_cancel_service.is_stop_requested(ORG, CONV))
        pushed.append(frame)

    reporter.push_frame = _capture  # type: ignore[method-assign]
    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
    assert armed_when_pushed and all(armed_when_pushed)
    reporter._tts_service.release.set()
    await reporter.settle_barge_in()


@pytest.mark.asyncio
async def test_idle_turn_start_arms_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_turn_cancel_service, "get_redis_client", lambda _s=None: None)
    reporter = ElevenLabsInterruptReporter(
        settings=SimpleNamespace(), org_id=ORG, user_id=USER, conversation_id=CONV,
        voice_session=VoicePipelineSession(),
    )
    await BaseObject.setup(reporter, TaskManager())

    async def _noop(*_a: Any, **_k: Any) -> None:
        return None

    reporter.push_frame = _noop  # type: ignore[method-assign]
    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
    assert chat_turn_cancel_service.is_stop_requested(ORG, CONV) is False


# --- 2/3. Reply identity of outbound audio ------------------------------------


def _audio(context_id: str | None = None) -> TTSAudioRawFrame:
    return TTSAudioRawFrame(b"\x01\x02" * 160, 16000, 1, context_id=context_id)


async def _stamper(session: VoicePipelineSession) -> tuple[ReplyAudioStampProcessor, list[Frame]]:
    stamper = ReplyAudioStampProcessor(voice_session=session)
    await BaseObject.setup(stamper, TaskManager())
    out: list[Frame] = []

    async def _capture(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        out.append(frame)

    stamper.push_frame = _capture  # type: ignore[method-assign]
    return stamper, out


def _start(reply_id: int) -> LLMFullResponseStartFrame:
    frame = LLMFullResponseStartFrame()
    setattr(frame, "gravitre_reply_id", reply_id)
    return frame


async def _transport(serializer: GravitreJsonAudioSerializer, frames: list[Frame]) -> list[int | None]:
    """What the websocket output does: rebuild audio frames, serialize in order."""
    ids: list[int | None] = []
    for frame in frames:
        if isinstance(frame, OutputAudioRawFrame):
            rebuilt = OutputAudioRawFrame(audio=frame.audio, sample_rate=16000, num_channels=1)
            ids.append(json.loads(await serializer.serialize(rebuilt)).get("reply_id"))
        elif isinstance(frame, (OutputTransportMessageFrame, InterruptionFrame)):
            payload = await serializer.serialize(frame)
            if isinstance(frame, OutputTransportMessageFrame) and frame.message.get("type") == REPLY_AUDIO_MARK:
                assert payload is None, "the reply mark must never reach the browser"
    return ids


@pytest.mark.asyncio
async def test_old_reply_frames_keep_the_old_id_after_a_new_reply_begins() -> None:
    session = VoicePipelineSession()
    stamper, out = await _stamper(session)
    serializer = GravitreJsonAudioSerializer(session=session)

    session.begin_reply()  # reply 1
    await stamper.process_frame(_start(1), FrameDirection.DOWNSTREAM)
    await stamper.process_frame(TTSStartedFrame(context_id="c1"), FrameDirection.DOWNSTREAM)
    await stamper.process_frame(_audio("c1"), FrameDirection.DOWNSTREAM)
    # Reply 2 begins while reply 1's audio is still arriving.
    session.begin_reply()
    await stamper.process_frame(_start(2), FrameDirection.DOWNSTREAM)
    await stamper.process_frame(_audio("c1"), FrameDirection.DOWNSTREAM)  # late, old context
    await stamper.process_frame(TTSStartedFrame(context_id="c2"), FrameDirection.DOWNSTREAM)
    await stamper.process_frame(_audio("c2"), FrameDirection.DOWNSTREAM)

    assert session.reply_id == 2
    assert await _transport(serializer, out) == [1, 1, 2]


@pytest.mark.asyncio
async def test_send_time_session_id_was_the_bug() -> None:
    """Without the stamp processor the serializer falls back to the session id: the old behaviour."""
    session = VoicePipelineSession()
    serializer = GravitreJsonAudioSerializer(session=session)
    session.begin_reply()
    session.begin_reply()
    late_old_frame = OutputAudioRawFrame(audio=b"\x00\x01" * 160, sample_rate=16000, num_channels=1)
    assert json.loads(await serializer.serialize(late_old_frame))["reply_id"] == 2


@pytest.mark.asyncio
async def test_cancelled_reply_audio_is_dropped_and_never_escapes_with_the_new_id() -> None:
    session = VoicePipelineSession()
    stamper, out = await _stamper(session)
    serializer = GravitreJsonAudioSerializer(session=session)
    tts = _SlowTTS()
    tts._turn_context_id = "c0"  # reply 1's context: no audio of it seen yet
    reporter, _pushed = await _live_reporter(tts, session)  # begins reply 1
    await stamper.process_frame(_start(1), FrameDirection.DOWNSTREAM)

    # Barge-in on reply 1 before any of its audio reached the stamp processor.
    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
    await stamper.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
    assert session.cancelled_through_reply_id == 1

    # Reply 2 opens; then reply 1's late audio arrives (context c0, and c1
    # which was never seen at all before the cut-off), then reply 2's audio.
    session.begin_reply()
    await stamper.process_frame(_start(2), FrameDirection.DOWNSTREAM)
    await stamper.process_frame(_audio("c0"), FrameDirection.DOWNSTREAM)
    await stamper.process_frame(TTSStartedFrame(context_id="c2"), FrameDirection.DOWNSTREAM)
    await stamper.process_frame(_audio("c2"), FrameDirection.DOWNSTREAM)

    ids = await _transport(serializer, out)
    assert ids == [2], "only reply 2's audio may be sent"
    assert stamper.dropped_frames == 1
    tts.release.set()
    await reporter.settle_barge_in()


@pytest.mark.asyncio
async def test_no_audio_after_cancellation_carries_a_newer_id_than_its_own() -> None:
    """Property check over an interleaving: every serialized frame's id matches its generator."""
    session = VoicePipelineSession()
    stamper, out = await _stamper(session)
    serializer = GravitreJsonAudioSerializer(session=session)
    expected: list[int] = []

    for reply in (1, 2, 3):
        session.begin_reply()
        await stamper.process_frame(_start(reply), FrameDirection.DOWNSTREAM)
        await stamper.process_frame(TTSStartedFrame(context_id=f"c{reply}"), FrameDirection.DOWNSTREAM)
        await stamper.process_frame(_audio(f"c{reply}"), FrameDirection.DOWNSTREAM)
        expected.append(reply)
        if reply == 2:
            # Barge-in cuts reply 2 off; its trailing audio arrives later.
            session.cancel_reply_audio(2)
            await stamper.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
            await stamper.process_frame(_audio("c2"), FrameDirection.DOWNSTREAM)
    # Late frames of every earlier reply, after reply 3 began.
    await stamper.process_frame(_audio("c1"), FrameDirection.DOWNSTREAM)
    await stamper.process_frame(_audio("c2"), FrameDirection.DOWNSTREAM)
    await stamper.process_frame(_audio("c3"), FrameDirection.DOWNSTREAM)
    expected.append(3)

    ids = await _transport(serializer, out)
    assert ids == expected
    assert 2 not in ids[ids.index(3):], "no cut-off audio after its cancellation"
    assert all(i is not None for i in ids)


@pytest.mark.asyncio
async def test_unmarked_frame_after_interruption_is_labelled_as_the_cut_off_reply() -> None:
    session = VoicePipelineSession()
    serializer = GravitreJsonAudioSerializer(session=session)
    from app.services.pipecat_voice.json_audio_serializer import reply_audio_mark

    session.begin_reply()
    assert await serializer.serialize(reply_audio_mark(1)) is None
    session.cancel_reply_audio(1)
    await serializer.serialize(InterruptionFrame())
    session.begin_reply()  # reply 2 is now current
    stale = OutputAudioRawFrame(audio=b"\x00\x01" * 160, sample_rate=16000, num_channels=1)
    assert json.loads(await serializer.serialize(stale))["reply_id"] == 1


# --- The tool layer: last stop check and the write effect record ---------------


def _invoke(monkeypatch: pytest.MonkeyPatch, impl) -> Any:
    from unittest.mock import MagicMock, patch

    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    monkeypatch.setattr(chat_turn_cancel_service, "get_redis_client", lambda _s=None: None)
    ctx = ToolContext(
        settings=SimpleNamespace(
            disable_connectors=False,
            connector_secrets_encryption_key="k" * 32,
            private_connector_runtime_enabled=True,
        ),
        client=MagicMock(),
        org_id=ORG,
        actor_id=USER,
        conversation_id=CONV,
    )
    with patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda _c, _a, p: p), patch(
        "app.services.read_preflight.enforce_invoke_preflight", side_effect=lambda _c, _a, p: p
    ), patch("app.services.tool_service._TOOL_REGISTRY", {WRITE_ACTION: impl}), patch(
        "app.services.tool_service.write_audit_event"
    ), patch("app.services.tool_service.time.sleep"):
        return invoke_tool(ctx, WRITE_ACTION, {})


def test_completed_write_is_recorded_as_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.tool_types import NormalizedResult
    from app.services.voice_barge_in_write import write_effects_since

    result = _invoke(monkeypatch, lambda *_a, **_k: NormalizedResult(success=True, action=WRITE_ACTION, data={}))
    assert result.success is True
    assert [(e["action"], e["status"]) for e in write_effects_since(ORG, CONV, 0.0)] == [(WRITE_ACTION, "completed")]


def test_stop_armed_before_the_provider_call_refuses_it(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.voice_barge_in_write import write_effects_since

    called: list[bool] = []
    chat_turn_cancel_service.arm_local_stop(ORG, CONV)
    with pytest.raises(ToolValidationError) as exc:
        _invoke(monkeypatch, lambda *_a, **_k: called.append(True))
    assert exc.value.code == WRITE_COMMIT_INTERRUPTED
    assert called == [], "the provider was never called"
    assert [e["status"] for e in write_effects_since(ORG, CONV, 0.0)] == ["blocked"]


def test_stop_armed_after_the_first_check_is_caught_at_the_last_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """The barge-in lands while invoke_tool is still in its permission/limit checks."""
    called: list[bool] = []

    def _limits_then_barge_in(_ctx: Any, _action: str) -> None:
        chat_turn_cancel_service.arm_local_stop(ORG, CONV)

    monkeypatch.setattr(
        "app.services.agent_guardrail_limits.enforce_agent_guardrail_limits", _limits_then_barge_in
    )
    with pytest.raises(ToolValidationError) as exc:
        _invoke(monkeypatch, lambda *_a, **_k: called.append(True))
    assert exc.value.code == WRITE_COMMIT_INTERRUPTED
    assert called == []


def test_stop_armed_during_the_provider_call_cannot_undo_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """A write already at the provider finishes; it is recorded as done, never as stopped."""
    from app.services.tool_types import NormalizedResult
    from app.services.voice_barge_in_write import write_effects_since

    def _provider(*_a: Any, **_k: Any) -> NormalizedResult:
        chat_turn_cancel_service.arm_local_stop(ORG, CONV)  # the barge-in lands mid-call
        return NormalizedResult(success=True, action=WRITE_ACTION, data={})

    assert _invoke(monkeypatch, _provider).success is True
    assert [e["status"] for e in write_effects_since(ORG, CONV, 0.0)] == ["completed"]
