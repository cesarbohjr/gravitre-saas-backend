"""A stop reaches the work it stops, and later turns can never undo it.

1. "cancel it", "stop" or a correction that arrives late, after a wordless
   start was held while the brain worked in silence, cancels the running
   turn's work at once. Before, the words were only queued as the next turn,
   behind the work they were meant to stop, and no write fence was armed.
2. Cancellation is scoped to the turn's work, not the conversation. A new
   turn or a reconnect releases the conversation stop marker; a worker of the
   cancelled turn that reaches its provider call afterwards is still refused,
   while the new turn's writes go through.
"""
from __future__ import annotations

import asyncio
import contextvars
import threading
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pipecat.frames.frames import (
    InterruptionFrame,
    LLMFullResponseStartFrame,
    OutputTransportMessageUrgentFrame,
    ProposedUserStartedSpeakingFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.services import chat_turn_cancel_service
from app.services.pipecat_voice.backchannel_turn_strategy import (
    BackchannelAwareUserTurnStartStrategy,
)
from app.services.pipecat_voice.interrupt_reporter import ElevenLabsInterruptReporter
from app.services.pipecat_voice.speculative_generation import start_speculative_run
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession
from app.services.pipecat_voice.voice_silence_guard import (
    TURN_CANCELLED,
    with_silence_ticks,
)
from app.services.react_write_gate import WRITE_COMMIT_INTERRUPTED
from app.services.tool_types import ToolValidationError
from app.services.turn_cancellation import (
    TurnCancellation,
    bound_turn_cancellation,
    current_turn_cancelled,
)

ORG = "00000000-0000-4000-8000-0000000000a1"
USER = "00000000-0000-4000-8000-0000000000c3"
CONV = "00000000-0000-4000-8000-0000000000e5"
WRITE_ACTION = "email.send"


@pytest.fixture(autouse=True)
def _no_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_turn_cancel_service, "get_redis_client", lambda _s=None: None)
    chat_turn_cancel_service.reset_local_stops_for_tests()
    from app.services.voice_barge_in_write import reset_write_effects_for_tests

    reset_write_effects_for_tests()


def _invoke_write(provider: Any) -> Any:
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

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
    ), patch("app.services.tool_service._TOOL_REGISTRY", {WRITE_ACTION: provider}), patch(
        "app.services.tool_service.write_audit_event"
    ), patch("app.services.tool_service.time.sleep"):
        return invoke_tool(ctx, WRITE_ACTION, {})


def _sent() -> Any:
    from app.services.tool_types import NormalizedResult

    return NormalizedResult(success=True, action=WRITE_ACTION, data={})


# --- 1. Late stop words after a wordless hold ---------------------------------


class _Recorder:
    def __init__(self) -> None:
        self.turn_started_calls: list[Any] = []
        self.reset_aggregation_calls = 0

    async def on_user_turn_started(self, _strategy: Any, params: Any) -> None:
        self.turn_started_calls.append(params)

    async def on_reset_aggregation(self, _strategy: Any) -> None:
        self.reset_aggregation_calls += 1

    async def noop(self, *_args: Any, **_kwargs: Any) -> None:
        return None


async def _held_while_thinking() -> tuple[BackchannelAwareUserTurnStartStrategy, _Recorder, VoicePipelineSession]:
    session = VoicePipelineSession()
    session.assistant_generating = True  # the brain is working; nothing plays
    strategy = BackchannelAwareUserTurnStartStrategy(
        enable_interruptions=True, grace_period_s=0.05, voice_session=session
    )
    await BaseObject.setup(strategy, TaskManager())
    recorder = _Recorder()
    strategy.add_event_handler("on_user_turn_started", recorder.on_user_turn_started)
    strategy.add_event_handler("on_reset_aggregation", recorder.on_reset_aggregation)
    strategy.add_event_handler("on_push_frame", recorder.noop)
    strategy.add_event_handler("on_broadcast_frame", recorder.noop)
    await strategy.process_frame(ProposedUserStartedSpeakingFrame())
    await asyncio.sleep(0.15)  # grace runs out with no words: held as noise
    assert recorder.turn_started_calls[0].enable_interruptions is False
    return strategy, recorder, session


def _final(text: str) -> TranscriptionFrame:
    return TranscriptionFrame(text=text, user_id="u1", timestamp="2026-10-10T00:00:00Z")


@pytest.mark.asyncio
@pytest.mark.parametrize("words", ["cancel it", "stop", "never mind", "actually make it Thursday"])
async def test_late_stop_words_cancel_the_running_work_at_once(words: str) -> None:
    strategy, recorder, session = await _held_while_thinking()
    running = TurnCancellation()
    session.bind_turn_work(running)

    await strategy.process_frame(_final(words))

    assert running.cancelled, "cancelled before the words are even queued as a turn"
    assert session.held_speech_escalations == 1
    assert recorder.reset_aggregation_calls == 0, "the words still become the next turn"
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_a_new_request_while_thinking_leaves_the_work_running() -> None:
    strategy, _recorder, session = await _held_while_thinking()
    running = TurnCancellation()
    session.bind_turn_work(running)

    await strategy.process_frame(_final("and also check Mike's calendar"))

    assert not running.cancelled
    assert session.held_speech_escalations == 1
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_filler_while_thinking_cancels_nothing() -> None:
    strategy, _recorder, session = await _held_while_thinking()
    running = TurnCancellation()
    session.bind_turn_work(running)

    await strategy.process_frame(_final("you there?"))

    assert not running.cancelled
    await strategy.cleanup()


@pytest.mark.asyncio
async def test_late_cancel_refuses_an_approved_write_on_its_way_to_the_provider() -> None:
    """Acceptance: wordless start, grace expires, final "cancel it" while the
    approved write is still in its pre-provider checks. Nothing is sent."""
    strategy, _recorder, session = await _held_while_thinking()
    running = TurnCancellation()
    session.bind_turn_work(running)
    at_checks = threading.Event()
    go_on = threading.Event()
    called: list[bool] = []

    def _limits(_ctx: Any, _action: str) -> None:
        at_checks.set()
        assert go_on.wait(5)

    def _worker() -> Any:
        with patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits", _limits):
            return _invoke_write(lambda *_a, **_k: called.append(True) or _sent())

    with bound_turn_cancellation(running):
        write = asyncio.ensure_future(asyncio.to_thread(_worker))
    assert await asyncio.to_thread(at_checks.wait, 5)

    await strategy.process_frame(_final("cancel it"))
    go_on.set()

    with pytest.raises(ToolValidationError) as refused:
        await write
    assert refused.value.code == WRITE_COMMIT_INTERRUPTED
    assert called == [], "the provider was never called"
    # The cancel turn and a follow-up release the conversation marker; the
    # cancelled work stays cancelled.
    chat_turn_cancel_service.clear_stop(ORG, CONV)
    assert running.cancelled
    await strategy.cleanup()


# --- 2. A later turn or a reconnect never un-cancels old work -----------------

_marker: contextvars.ContextVar[str] = contextvars.ContextVar("test_marker", default="")


def test_old_worker_stays_refused_after_the_marker_is_released() -> None:
    """Acceptance: block an old worker right before invoke, cancel it, start
    another turn (or reconnect), then release the worker."""
    old = TurnCancellation()
    at_invoke = threading.Event()
    release = threading.Event()
    outcome: dict[str, Any] = {}
    called: list[str] = []

    def _limits(_ctx: Any, _action: str) -> None:
        if contextvars.copy_context().get(_marker) == "old":
            at_invoke.set()
            assert release.wait(5)

    def _old_worker() -> None:
        _marker.set("old")
        try:
            with bound_turn_cancellation(old):
                outcome["old"] = _invoke_write(lambda *_a, **_k: called.append("old") or _sent())
        except ToolValidationError as exc:
            outcome["old"] = exc

    with patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits", _limits):
        thread = threading.Thread(target=_old_worker, daemon=True)
        thread.start()
        assert at_invoke.wait(5)

        # Barge-in: the old turn's work is cancelled and the marker armed.
        old.cancel("barge_in")
        chat_turn_cancel_service.arm_local_stop(ORG, CONV)
        # The next ordinary turn (settle_barge_in) or a reconnect releases it.
        chat_turn_cancel_service.clear_stop(ORG, CONV)

        # The new turn's write goes through.
        with bound_turn_cancellation(TurnCancellation()):
            assert _invoke_write(lambda *_a, **_k: called.append("new") or _sent()).success

        release.set()
        thread.join(5)

    assert isinstance(outcome["old"], ToolValidationError)
    assert outcome["old"].code == WRITE_COMMIT_INTERRUPTED
    assert called == ["new"], "the cancelled turn's write never reached the provider"


def test_cancelling_is_final_and_reports_once() -> None:
    token = TurnCancellation()
    assert token.cancel("barge_in") is True
    assert token.cancel("task_cancel") is False
    assert token.cancelled and token.reason == "barge_in"
    assert TurnCancellation().generation > token.generation


def test_the_token_follows_threads_and_stays_out_of_other_turns() -> None:
    token = TurnCancellation()
    token.cancel("barge_in")
    assert current_turn_cancelled() is False

    async def _inside() -> bool:
        return await asyncio.to_thread(current_turn_cancelled)

    with bound_turn_cancellation(token):
        assert asyncio.run(_inside()) is True
        assert chat_turn_cancel_service.is_stop_requested(ORG, CONV) is True
    assert chat_turn_cancel_service.is_stop_requested(ORG, CONV) is False


def test_the_token_crosses_the_async_bridge() -> None:
    from app.core.async_bridge import run_coro_sync

    token = TurnCancellation()
    token.cancel("barge_in")

    async def _check() -> bool:
        return current_turn_cancelled()

    async def _from_loop() -> bool:
        # run_coro_sync from a worker thread of a running loop uses the bridge loop.
        return await asyncio.to_thread(run_coro_sync, _check())

    with bound_turn_cancellation(token):
        assert asyncio.run(_from_loop()) is True


@pytest.mark.asyncio
async def test_barge_in_cancels_the_interrupted_turns_work() -> None:
    session = VoicePipelineSession()
    reporter = ElevenLabsInterruptReporter(
        settings=SimpleNamespace(), org_id=ORG, user_id=USER, conversation_id=CONV, voice_session=session
    )
    await BaseObject.setup(reporter, TaskManager())

    async def _noop(*_a: Any, **_k: Any) -> None:
        return None

    reporter.push_frame = _noop  # type: ignore[method-assign]
    reporter._cancel_tts_context = _noop  # type: ignore[method-assign]
    running = TurnCancellation()
    session.bind_turn_work(running)
    reporter.begin_turn("Email Sarah the deck")
    session.begin_reply()
    await reporter.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await reporter.process_frame(
        OutputTransportMessageUrgentFrame(message={"type": "assistant_text", "delta": "Sending it now."}),
        FrameDirection.DOWNSTREAM,
    )
    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
    assert running.cancelled and running.reason == "barge_in"
    await reporter.settle_barge_in()
    assert running.cancelled, "the next turn releases the marker, never the token"


@pytest.mark.asyncio
async def test_idle_turn_start_cancels_nothing() -> None:
    session = VoicePipelineSession()
    reporter = ElevenLabsInterruptReporter(
        settings=SimpleNamespace(), org_id=ORG, user_id=USER, conversation_id=CONV, voice_session=session
    )
    await BaseObject.setup(reporter, TaskManager())

    async def _noop(*_a: Any, **_k: Any) -> None:
        return None

    reporter.push_frame = _noop  # type: ignore[method-assign]
    finished = TurnCancellation()
    session.bind_turn_work(finished)
    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
    assert not finished.cancelled


# --- Speculative runs and the turn loop wake-up -------------------------------


@pytest.mark.asyncio
async def test_a_discarded_speculative_run_cancels_its_own_work() -> None:
    started = asyncio.Event()

    async def _runner():
        started.set()
        await asyncio.sleep(10)
        yield "never"

    run = start_speculative_run(text="email sarah", runner=_runner, create_task=asyncio.ensure_future)
    await started.wait()
    run.cancel()
    assert run.cancellation.cancelled
    assert run.cancellation.reason == "speculative_discarded"


@pytest.mark.asyncio
async def test_an_adopted_run_is_cancelled_with_the_turn_that_adopted_it() -> None:
    seen: list[bool] = []
    go = asyncio.Event()

    async def _runner():
        await go.wait()
        seen.append(current_turn_cancelled())
        yield "done"

    run = start_speculative_run(text="email sarah", runner=_runner, create_task=asyncio.ensure_future)
    run.mark_adopted()
    turn = TurnCancellation()
    turn.link(run.cancellation)
    turn.cancel("held_task_cancel")
    go.set()
    await run.task
    assert seen == [True], "the producer's own context sees the cancel"
    late = TurnCancellation()
    turn.link(late)
    assert late.cancelled, "linking to an already cancelled turn cancels at once"


@pytest.mark.asyncio
async def test_the_turn_loop_wakes_on_cancel_during_a_silent_tool_call() -> None:
    async def _silent_tool():
        await asyncio.sleep(30)
        yield "late"

    token = TurnCancellation()
    loop = asyncio.get_running_loop()
    loop.call_later(0.05, token.cancel, "held_task_cancel")
    started = loop.time()
    stream = with_silence_ticks(_silent_tool(), interval_s=4.0, cancelled=token.waiter())
    first = await stream.__anext__()
    assert first is TURN_CANCELLED
    assert loop.time() - started < 1.0, "not after the 4 s silence tick"
    await stream.aclose()


@pytest.mark.asyncio
async def test_cancel_from_a_worker_thread_wakes_the_loop() -> None:
    token = TurnCancellation()
    waiter = token.waiter()
    await asyncio.to_thread(token.cancel, "barge_in")
    await asyncio.wait_for(waiter.wait(), 1.0)


def test_a_stopped_turn_says_nothing_left_over() -> None:
    """After a stop, the unfinished clause still buffered is not spoken."""
    from unittest.mock import AsyncMock

    from app.operators.stream_events import (
        AssistantStreamComplete,
        AssistantStreamEvent,
    )
    from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService

    service = GravitreCognitiveLLMService(app_settings=object(), org_id=ORG, user_id=USER)
    token = TurnCancellation()
    service._turn_work = token

    async def _stream(**_kwargs: Any):
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Your revenue was up "})
        token.cancel("held_task_cancel")
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "twelve percent."})
        yield AssistantStreamComplete(full_content="x", tool_results=[], react_result=None, model="t")

    spoken: list[str] = []
    service.push_frame = AsyncMock()
    service._push_llm_text = AsyncMock(side_effect=lambda text: spoken.append(text))

    class _Context:
        def get_messages(self) -> list[dict[str, Any]]:
            return [{"role": "user", "content": "how is revenue"}]

    intelligence = SimpleNamespace(execute_task_streaming=_stream)
    with patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=intelligence):
        asyncio.run(service._run_gravitre_turn(_Context()))

    assert spoken == [], "the buffered 'Your revenue was up' is dropped, not flushed"
