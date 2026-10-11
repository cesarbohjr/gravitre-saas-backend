"""voice_explain_aside_v1: "what does that mean?" while a task is still running.

The task keeps running and completes exactly once. The explanation is spoken
as an aside under its own reply, and cannot write anything. The task's result
is spoken once after the aside (only shown if the user moved on). Cancelling
the task ends the aside with it, a failed aside never costs the task its
result, and a real barge-in cuts the aside off.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pipecat.frames.frames import (
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    OutputTransportMessageUrgentFrame,
)
from pipecat.processors.frame_processor import FrameDirection

from app.services.pipecat_voice.transcript_relay import classify_non_turn_final
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession
from app.services.speculative_execution import defer_if_speculative
from tests.services.pipecat_voice.test_interrupt_intents import (  # noqa: F401 - autouse fixture
    _final,
    _Harness,
    _interim,
    _isolated,
    _strategy,
)

REQUEST = "pull last month's ads report"
QUESTION = "what does that mean"
RESULT = "Conversions were up twelve percent."
ASIDE = "Conversions are the sign-ups that came from your ads."


# --- the aside in the brain service -----------------------------------------------


class _AsideHarness(_Harness):
    """Turn 1 runs a slow lookup; the test asks the aside while it runs."""

    def __init__(self, *, aside_on: bool = True) -> None:
        super().__init__(True)
        self.settings.voice_explain_aside_v1 = aside_on
        self.lookup_runs = 0
        self.lookup_release = asyncio.Event()
        self.aside_release = asyncio.Event()
        self.aside_release.set()
        self.aside_started = asyncio.Event()
        self.aside_writes: list[str] = []
        self.aside_raises = False
        self.during_lookup: Any = None
        self.after_lookup: Any = None
        self.result_text = RESULT

        async def _yielding_push(*_a: Any, **_k: Any) -> None:
            # A real pipeline push can suspend; interleavings must stay well-formed.
            await asyncio.sleep(0)

        self.service.push_frame.side_effect = _yielding_push

    def run(self, script) -> None:
        async def _bounded() -> None:
            # A broken fence shows up as a hang; fail instead.
            await asyncio.wait_for(script(), timeout=10)

        super().run(_bounded)

    async def _stream(self, **kwargs: Any):
        from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent

        self.calls.append(kwargs)
        if kwargs.get("query") == QUESTION:
            self.aside_started.set()
            # An aside that tries to act: it must never land.
            defer_if_speculative("test.write", lambda: self.aside_writes.append("written"))
            if self.aside_raises:
                raise RuntimeError("aside brain failed")
            yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Conversions are the sign-ups "})
            await self.aside_release.wait()
            yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "that came from your ads."})
            yield AssistantStreamComplete(full_content=ASIDE, tool_results=[], react_result=None, model="t")
            return
        self.lookup_runs += 1
        yield AssistantStreamEvent(
            sse_type="tool-input-available", payload={"toolCallId": "c1", "toolName": "google_ads_report"}
        )
        if self.during_lookup is not None:
            await self.during_lookup()
        await self.lookup_release.wait()
        yield AssistantStreamEvent(
            sse_type="tool-output-available", payload={"toolCallId": "c1", "output": {"conversions": 112}}
        )
        if self.after_lookup is not None:
            await self.after_lookup()
        if self.result_text:
            yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": self.result_text})
        yield AssistantStreamComplete(full_content=self.result_text, tool_results=[], react_result=None, model="t")

    def spoken(self) -> list[str]:
        return [call.args[0] for call in self.service._push_llm_text.await_args_list]

    def frames(self, cls) -> list[Any]:
        return [c.args[0] for c in self.service.push_frame.await_args_list if isinstance(c.args[0], cls)]

    def messages(self, kind: str) -> list[dict[str, Any]]:
        return [f.message for f in self.frames(OutputTransportMessageUrgentFrame) if f.message.get("type") == kind]

    def response_frames(self) -> list[str]:
        out = []
        for call in self.service.push_frame.await_args_list:
            frame = call.args[0]
            if isinstance(frame, LLMFullResponseStartFrame):
                out.append(f"start:{getattr(frame, 'gravitre_reply_id', None)}")
            elif isinstance(frame, LLMFullResponseEndFrame):
                out.append("end")
        return out


def _ask_aside_then_finish(h: _AsideHarness) -> None:
    async def _during() -> None:
        # The user asks while the lookup runs (the turn strategy's call).
        h.session.note_user_turn_start()
        assert h.service.start_explain_aside(QUESTION)
        await h.aside_started.wait()
        await asyncio.sleep(0)
        h.lookup_release.set()

    h.during_lookup = _during


def _well_nested(frames: list[str]) -> bool:
    open_reply = False
    for item in frames:
        if item.startswith("start"):
            if open_reply:
                return False
            open_reply = True
        else:
            if not open_reply:
                return False
            open_reply = False
    return not open_reply


def test_the_task_keeps_running_and_its_result_is_spoken_once_after_the_aside() -> None:
    h = _AsideHarness()
    _ask_aside_then_finish(h)
    h.run(lambda: h.turn(REQUEST))

    assert h.lookup_runs == 1, "the lookup ran exactly once"
    spoken = " ".join(h.spoken())
    assert "Conversions are the sign-ups" in spoken and "that came from your ads." in spoken
    assert spoken.count(RESULT) == 1, "the task's result is spoken once"
    assert spoken.index("that came from your ads.") < spoken.index(RESULT), "never over the aside"
    frames = h.response_frames()
    assert _well_nested(frames), frames
    # Task reply 1 (silenced), aside 2, task reopened silent 3, result 4.
    assert frames == ["start:1", "end", "start:2", "end", "start:3", "end", "start:4", "end"]
    assert h.session.reply_muted(1) and h.session.reply_muted(3) and not h.session.reply_muted(4)
    assert not h.session.reply_muted(2), "the aside itself is heard"
    done = [m for m in h.messages("assistant_turn.complete") if m.get("aside")]
    assert done and done[0]["user_text"] == QUESTION and done[0]["cancelled"] is False
    assert [p["user_text"] for p in h.persisted] == [QUESTION, REQUEST]
    assert h.persisted[-1]["assistant_text"] == RESULT


def test_the_aside_explains_from_the_running_task_and_cannot_act() -> None:
    h = _AsideHarness()

    async def _during() -> None:
        h.session.note_user_turn_start()
        h.lookup_release.set()

    async def _after() -> None:
        # Asked once the lookup returned: its result is a fact for the aside.
        assert h.service.start_explain_aside(QUESTION)
        await h.aside_started.wait()

    h.during_lookup = _during
    h.after_lookup = _after
    h.run(lambda: h.turn(REQUEST))

    aside_call = next(c for c in h.calls if c.get("query") == QUESTION)
    prompt = str(aside_call.get("assistant_base_prompt") or "")
    assert REQUEST in prompt and "conversions" in prompt and "112" in prompt
    assert h.aside_writes == [], "the aside's write was discarded"
    aside_deltas = [m for m in h.messages("assistant_text") if m.get("aside")]
    assert "".join(m["delta"] for m in aside_deltas).strip().startswith("Conversions are")
    assert all(not m.get("aside") for m in h.messages("assistant_text") if RESULT in m.get("delta", ""))


def test_a_task_that_finishes_during_the_aside_waits_for_it() -> None:
    h = _AsideHarness()
    h.aside_release.clear()

    async def _during() -> None:
        h.session.note_user_turn_start()
        assert h.service.start_explain_aside(QUESTION)
        await h.aside_started.wait()
        h.lookup_release.set()

    h.during_lookup = _during

    async def _script() -> None:
        turn = asyncio.create_task(h.turn(REQUEST))
        await h.aside_started.wait()
        # Let the task finish its work while the aside is mid-sentence.
        for _ in range(20):
            await asyncio.sleep(0)
        assert not turn.done(), "the turn waits for the aside before it ends"
        h.aside_release.set()
        await turn

    h.run(_script)
    spoken = " ".join(h.spoken())
    assert spoken.count(RESULT) == 1
    assert spoken.index("that came from your ads.") < spoken.index(RESULT)
    assert _well_nested(h.response_frames()), h.response_frames()
    assert h.lookup_runs == 1


def test_a_task_with_nothing_left_to_say_still_closes_after_the_aside() -> None:
    h = _AsideHarness()
    h.result_text = ""
    h.aside_release.clear()

    async def _during() -> None:
        h.session.note_user_turn_start()
        assert h.service.start_explain_aside(QUESTION)
        await h.aside_started.wait()
        h.lookup_release.set()

    h.during_lookup = _during

    ending = asyncio.Event()
    stop_answer_first = h.service._stop_answer_first

    async def _turn_ending() -> None:
        ending.set()
        await stop_answer_first()

    h.service._stop_answer_first = _turn_ending  # type: ignore[method-assign]

    async def _script() -> None:
        turn = asyncio.create_task(h.turn(REQUEST))
        await ending.wait()
        for _ in range(20):
            await asyncio.sleep(0)
        assert not turn.done(), "the turn waits for the aside before it ends"
        h.aside_release.set()
        await turn

    h.run(_script)
    assert "that came from your ads." in " ".join(h.spoken())
    assert _well_nested(h.response_frames()), h.response_frames()
    assert h.response_frames()[-1] == "end"


def test_the_result_is_only_shown_when_the_user_moved_on_after_the_aside() -> None:
    h = _AsideHarness()

    async def _during() -> None:
        h.session.note_user_turn_start()
        assert h.service.start_explain_aside(QUESTION)
        await h.aside_started.wait()
        await h.service._await_aside()
        h.session.note_user_turn_start()  # a new question after the aside
        h.lookup_release.set()

    h.during_lookup = _during
    h.run(lambda: h.turn(REQUEST))
    spoken = " ".join(h.spoken())
    assert RESULT not in spoken, "nothing is spoken over a user who went on"
    assert RESULT in h.spoken_client_text(), "the result is still shown"
    assert h.persisted[-1]["assistant_text"] == RESULT


def test_cancelling_the_task_ends_its_aside_and_no_stale_result_is_spoken() -> None:
    h = _AsideHarness()
    h.aside_release.clear()

    async def _during() -> None:
        h.session.note_user_turn_start()
        assert h.service.start_explain_aside(QUESTION)
        await h.aside_started.wait()
        # "Cancel it" during the aside: the strategy cancels the turn's work.
        assert h.session.cancel_turn_work("held_task_cancel")
        h.lookup_release.set()

    h.during_lookup = _during
    h.run(lambda: h.turn(REQUEST))
    spoken = " ".join(h.spoken())
    assert RESULT not in spoken and "that came from your ads." not in spoken
    done = [m for m in h.messages("assistant_turn.complete") if m.get("aside")]
    assert done and done[0]["cancelled"] is True
    assert [p["user_text"] for p in h.persisted] == [], "neither the aside nor the cancelled task is stored"
    assert _well_nested(h.response_frames()), h.response_frames()


def test_a_failed_aside_says_so_and_the_task_still_delivers() -> None:
    h = _AsideHarness()
    h.aside_raises = True
    _ask_aside_then_finish(h)
    h.run(lambda: h.turn(REQUEST))
    spoken = " ".join(h.spoken())
    assert "I couldn't answer that just now" in spoken
    assert spoken.count(RESULT) == 1
    assert h.lookup_runs == 1
    assert [p["user_text"] for p in h.persisted] == [REQUEST]


def test_a_refused_aside_says_the_guardrail_line_and_the_task_still_delivers() -> None:
    from app.services import shared_turn_preparation
    from app.services.shared_turn_preparation import SPOKEN_GUARDRAIL_MESSAGES, TurnGuardrailBlocked

    h = _AsideHarness()

    async def _during() -> None:
        h.session.note_user_turn_start()
        assert h.service.start_explain_aside(QUESTION)
        # A refused aside never reaches the brain; let it finish, then the task.
        aside = h.service._aside_task
        assert aside is not None
        await asyncio.wait({aside})
        h.lookup_release.set()

    h.during_lookup = _during

    async def _guard(*_a: Any, user_text: str = "", **_k: Any) -> None:
        if user_text == QUESTION:
            raise TurnGuardrailBlocked("blocked")

    async def _script() -> None:
        shared_turn_preparation.guard_spoken_turn.side_effect = _guard
        await h.turn(REQUEST)

    h.run(_script)
    spoken = " ".join(h.spoken())
    refusal = SPOKEN_GUARDRAIL_MESSAGES.get("blocked", SPOKEN_GUARDRAIL_MESSAGES["invalid"])
    assert refusal in spoken
    assert "I couldn't answer that just now" not in spoken
    assert spoken.count(RESULT) == 1
    assert h.lookup_runs == 1


def test_a_barge_in_cuts_the_aside_off() -> None:
    h = _AsideHarness()
    h.aside_release.clear()

    async def _during() -> None:
        h.session.note_user_turn_start()
        assert h.service.start_explain_aside(QUESTION)
        await h.aside_started.wait()
        await h.service.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
        await asyncio.wait_for(h.service._await_aside(), timeout=2)
        h.lookup_release.set()

    h.during_lookup = _during
    h.run(lambda: h.turn(REQUEST))
    assert "that came from your ads." not in " ".join(h.spoken())
    done = [m for m in h.messages("assistant_turn.complete") if m.get("aside")]
    assert done and done[0]["cancelled"] is True


def test_a_newer_aside_replaces_the_older_one() -> None:
    h = _AsideHarness()
    h.aside_release.clear()

    async def _during() -> None:
        h.session.note_user_turn_start()
        assert h.service.start_explain_aside(QUESTION)
        await h.aside_started.wait()
        first = h.service._aside_task
        h.aside_started.clear()
        # Replaced while still mid-answer: the old reply closes before the new opens.
        assert h.service.start_explain_aside(QUESTION)
        h.aside_release.set()
        assert first is not None and (first.cancelled() or first.done() or first.cancelling())
        await h.service._await_aside()
        h.lookup_release.set()

    h.during_lookup = _during
    h.run(lambda: h.turn(REQUEST))
    assert " ".join(h.spoken()).count(RESULT) == 1
    assert _well_nested(h.response_frames()), h.response_frames()


def test_flag_off_starts_no_aside() -> None:
    h = _AsideHarness(aside_on=False)
    assert h.service.start_explain_aside(QUESTION) is False


# --- turn taking ------------------------------------------------------------------


def _aside_session(*, work_active: bool = True, enabled: bool = True) -> tuple[VoicePipelineSession, list[str], list[str]]:
    session = VoicePipelineSession()
    session.explain_aside_enabled = enabled
    session.work_active = work_active
    asides: list[str] = []
    silenced: list[str] = []

    def _start(text: str) -> bool:
        asides.append(text)
        return True

    async def _silence() -> bool:
        silenced.append("aside")
        return True

    session.aside_handler = _start
    session.speech_aside_handler = _silence
    return session, asides, silenced


@pytest.mark.asyncio
async def test_an_explain_question_over_the_reply_becomes_an_aside() -> None:
    session, asides, silenced = _aside_session()
    strategy, rec, _ = await _strategy(True, session)
    await strategy.process_frame(_final(QUESTION))
    assert asides == [QUESTION]
    assert silenced == ["aside"], "what was playing is silenced, the work is not"
    assert rec.started[-1].enable_interruptions is False
    assert rec.resets == 1, "the words never become a turn"
    assert InterruptionFrame not in rec.broadcasts


@pytest.mark.asyncio
async def test_interim_words_hold_until_the_final_starts_the_aside() -> None:
    session, asides, _ = _aside_session()
    strategy, rec, _ = await _strategy(True, session)
    await strategy.process_frame(_interim("wait what does that mean"))
    assert asides == []
    await strategy.process_frame(_final("wait what does that mean"))
    assert asides == ["wait what does that mean"], "started once, with the final words"
    assert InterruptionFrame not in rec.broadcasts


@pytest.mark.asyncio
async def test_final_words_that_are_not_an_explanation_interrupt_after_all() -> None:
    session, asides, _ = _aside_session()
    strategy, rec, _ = await _strategy(True, session)
    await strategy.process_frame(_interim("wait what does that mean"))
    await strategy.process_frame(_final("wait what does that mean actually cancel it"))
    assert asides == []
    assert InterruptionFrame in rec.broadcasts


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("work_active", "enabled", "intents_on"),
    [(False, True, True), (True, False, True), (True, True, False)],
    ids=["no_running_work", "aside_flag_off", "intents_flag_off"],
)
async def test_no_aside_without_running_work_or_the_flags(work_active: bool, enabled: bool, intents_on: bool) -> None:
    session, asides, _ = _aside_session(work_active=work_active, enabled=enabled)
    strategy, rec, _ = await _strategy(intents_on, session)
    await strategy.process_frame(_final(QUESTION))
    assert asides == []
    assert rec.started[-1].enable_interruptions is True


@pytest.mark.asyncio
async def test_an_explain_question_while_thinking_becomes_an_aside() -> None:
    from pipecat.frames.frames import BotStoppedSpeakingFrame, ProposedUserStartedSpeakingFrame

    session, asides, silenced = _aside_session()
    session.assistant_generating = True  # type: ignore[attr-defined]
    strategy, rec, _ = await _strategy(True, session)
    await strategy.process_frame(BotStoppedSpeakingFrame())
    strategy._pending = False
    await strategy.process_frame(ProposedUserStartedSpeakingFrame())
    await strategy.process_frame(_final(QUESTION))
    assert asides == [QUESTION]
    assert silenced == [], "nothing was playing"
    assert InterruptionFrame not in rec.broadcasts


def test_the_browser_is_told_the_words_are_an_aside() -> None:
    session, _, _ = _aside_session()
    assert classify_non_turn_final(QUESTION, session) == "explain_aside"
    session.work_active = False
    assert classify_non_turn_final(QUESTION, session) is None
    session.work_active = True
    assert classify_non_turn_final("show me revenue by region", session) is None


def test_settings_default_off() -> None:
    from app.config import Settings

    assert Settings.model_fields["voice_explain_aside_v1"].default is False

