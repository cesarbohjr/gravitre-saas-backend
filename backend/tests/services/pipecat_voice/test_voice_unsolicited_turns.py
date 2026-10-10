"""Opening voice must never run a turn, a tool or a CRM answer nobody asked for.

Drives the real UtteranceGateProcessor, TextTurnKickProcessor, Pipecat user
aggregator and GravitreCognitiveLLMService through a Pipecat test pipeline,
against ``FakeSupabase`` seeded with a conversation whose last message is a
CRM question that never got an answer. The brain is a fake that records every
call and every tool it was asked to run; a turn is "run" when it is called.
Synthetic: no Deepgram, no ElevenLabs, no model.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from pipecat.frames.frames import (
    InterimTranscriptionFrame,
    LLMContextFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.tests.utils import SleepFrame, run_test
from pipecat.turns.user_start.external_user_turn_start_strategy import (
    ExternalUserTurnStartStrategy,
)
from pipecat.turns.user_stop.external_user_turn_stop_strategy import (
    ExternalUserTurnStopStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services import chat_turn_cancel_service
from app.services.pipecat_voice.cognitive_llm import (
    VOICE_NO_VOLUNTEERED_DATA_NOTE,
    GravitreCognitiveLLMService,
)
from app.services.pipecat_voice.llm_context_utils import messages_from_context
from app.services.pipecat_voice.speculative_generation import (
    SpeculativeGenerationCoordinator,
)
from app.services.pipecat_voice.speculative_prefetch import SpeculativePrefetchProcessor
from app.services.pipecat_voice.text_turn_kick import TextTurnKickProcessor
from app.services.pipecat_voice.utterance_gate import (
    UtteranceGateProcessor,
    average_word_confidence,
    is_non_utterance,
)
from tests.support.fake_supabase import FakeSupabase

ORG = "00000000-0000-4000-8000-0000000000a1"
USER = "00000000-0000-4000-8000-0000000000c3"
SETTINGS = SimpleNamespace()
CRM_QUESTION = "How many companies do we have in HubSpot?"
# What the org context could carry if a connector snapshot ever lands in it.
TURN_SETTLE_S = 0.8
PROMPT_WITH_CRM_STATS = "You are Gravitre.\n## Current Business Context\n- HubSpot: 1,234 companies"


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeSupabase:
    client = FakeSupabase()
    monkeypatch.setattr("app.workflows.repository.get_supabase_client", lambda _s: client)
    monkeypatch.setattr(chat_turn_cancel_service, "get_redis_client", lambda _s=None: None)
    monkeypatch.setattr(
        "app.services.shared_turn_preparation.build_turn_system_prompt",
        lambda *_a, **_k: PROMPT_WITH_CRM_STATS,
    )

    async def _no_guard(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr("app.services.shared_turn_preparation.guard_spoken_turn", _no_guard)
    chat_turn_cancel_service._local_stops.clear()
    return client


def _seed_unanswered_crm_question(db: FakeSupabase) -> str:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    db.tables.setdefault("conversation_messages", []).extend(
        [
            {"id": "m1", "conversation_id": conv, "role": "user", "content": "Priority account is Acme.", "created_at": "2026-10-07T10:00:00Z"},
            {"id": "m2", "conversation_id": conv, "role": "assistant", "content": "Noted: Acme first.", "created_at": "2026-10-07T10:00:01Z"},
            # Typed before Talk opened; the text turn never answered it.
            {"id": "m3", "conversation_id": conv, "role": "user", "content": CRM_QUESTION, "created_at": "2026-10-07T10:05:00Z"},
        ]
    )
    return conv


class _Brain:
    """Records each brain call; a CRM question in the query would trigger a HubSpot read."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.tool_calls: list[str] = []

    def execute_task_streaming(self, **kwargs: Any):
        self.calls.append(kwargs)
        brain = self

        async def _stream():
            if "hubspot" in str(kwargs.get("query") or "").lower():
                brain.tool_calls.append("hubspot_search_companies")
                yield AssistantStreamEvent(
                    sse_type="tool-input-available",
                    payload={"toolCallId": "t1", "toolName": "hubspot_search_companies"},
                )
            reply = "Hey! What can I help with?"
            yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": reply})
            yield AssistantStreamComplete(full_content=reply, tool_results=[], react_result=None, model="test")

        return _stream()


def _pipeline(conv: str) -> tuple[Pipeline, GravitreCognitiveLLMService]:
    llm = GravitreCognitiveLLMService(app_settings=SETTINGS, org_id=ORG, user_id=USER, conversation_id=conv)
    llm._persist_completed_voice_turn = lambda **_k: (None, None)  # type: ignore[method-assign]
    params: dict[str, Any] = {
        "user_turn_strategies": UserTurnStrategies(
            start=[ExternalUserTurnStartStrategy()], stop=[ExternalUserTurnStopStrategy()]
        )
    }
    if "empty_user_turn" in getattr(LLMUserAggregatorParams, "__dataclass_fields__", {}):
        params["empty_user_turn"] = None
    user_agg, _assistant_agg = LLMContextAggregatorPair(LLMContext(), user_params=LLMUserAggregatorParams(**params))
    pipeline = Pipeline(
        [UtteranceGateProcessor(app_settings=SETTINGS, org_id=ORG), TextTurnKickProcessor(), user_agg, llm]
    )
    return pipeline, llm


def _spoken(text: str, *, confidence: float | None = None) -> list[Any]:
    result = None
    if confidence is not None:
        result = {"words": [{"word": w, "confidence": confidence} for w in text.split()]}
    return [
        UserStartedSpeakingFrame(),
        TranscriptionFrame(text=text, user_id="flux", timestamp="", result=result, finalized=True),
        UserStoppedSpeakingFrame(),
        # ExternalUserTurnStopStrategy holds the stop up to 0.5 s for late text.
        SleepFrame(sleep=TURN_SETTLE_S),
    ]


async def _run(conv: str, frames: list[Any]) -> _Brain:
    brain = _Brain()
    pipeline, _llm = _pipeline(conv)
    with patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=brain):
        await run_test(pipeline, frames_to_send=[SleepFrame(sleep=0.05), *frames])
    return brain


@pytest.mark.asyncio
async def test_connect_with_unanswered_crm_question_runs_nothing_until_the_user_speaks(db: FakeSupabase) -> None:
    conv = _seed_unanswered_crm_question(db)
    brain = await _run(conv, [])
    assert brain.calls == [], "opening voice ran a brain turn with no user utterance"
    assert brain.tool_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("noise", ["Uh.", "um", "Hmm...", "mm-hmm", "uh huh", ".", "A"])
async def test_filler_or_noise_transcript_runs_no_turn(db: FakeSupabase, noise: str) -> None:
    conv = _seed_unanswered_crm_question(db)
    brain = await _run(conv, _spoken(noise))
    assert brain.calls == [], f"{noise!r} started a brain turn"
    assert brain.tool_calls == []


@pytest.mark.asyncio
async def test_low_confidence_short_transcript_runs_no_turn(db: FakeSupabase) -> None:
    conv = _seed_unanswered_crm_question(db)
    brain = await _run(conv, _spoken("yeah okay", confidence=0.2))
    assert brain.calls == []


@pytest.mark.asyncio
async def test_first_social_utterance_does_not_answer_the_stale_crm_question(db: FakeSupabase) -> None:
    conv = _seed_unanswered_crm_question(db)
    brain = await _run(conv, _spoken("Hey there", confidence=0.95))

    assert len(brain.calls) == 1
    call = brain.calls[0]
    assert call["query"] == "Hey there"
    history_text = " ".join(m["content"] for m in call["conversation_history"] or [])
    assert CRM_QUESTION not in history_text, "the pre-socket unanswered question was handed to the brain"
    assert [m["content"] for m in call["conversation_history"]] == ["Priority account is Acme.", "Noted: Acme first."]
    assert brain.tool_calls == [], "a connector call ran without the user asking for one"
    assert VOICE_NO_VOLUNTEERED_DATA_NOTE in str(call["assistant_base_prompt"])


@pytest.mark.asyncio
async def test_typed_text_in_this_socket_is_still_answered(db: FakeSupabase) -> None:
    conv = _seed_unanswered_crm_question(db)
    frames = [
        TranscriptionFrame(text=CRM_QUESTION, user_id="browser", timestamp="", finalized=True),
        SleepFrame(sleep=TURN_SETTLE_S),
    ]
    brain = await _run(conv, frames)
    assert len(brain.calls) == 1
    assert brain.calls[0]["query"] == CRM_QUESTION
    assert brain.tool_calls == ["hubspot_search_companies"]


@pytest.mark.asyncio
async def test_context_that_does_not_end_on_a_user_turn_is_not_answered(db: FakeSupabase) -> None:
    conv = _seed_unanswered_crm_question(db)
    llm = GravitreCognitiveLLMService(app_settings=SETTINGS, org_id=ORG, user_id=USER, conversation_id=conv)
    brain = _Brain()
    contexts = [
        # Re-pushed context after a finished turn.
        LLMContext(messages=[{"role": "user", "content": CRM_QUESTION}, {"role": "assistant", "content": "1,234."}]),
        # Pipecat empty-turn recovery note after an unanswered user message.
        LLMContext(messages=[{"role": "user", "content": CRM_QUESTION}, {"role": "developer", "content": "Ask them to repeat."}]),
        LLMContext(messages=[]),
    ]
    with patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=brain):
        for context in contexts:
            await llm._run_gravitre_turn(context)
    assert brain.calls == []


@pytest.mark.asyncio
async def test_provisional_speculation_context_frame_is_not_run(db: FakeSupabase) -> None:
    conv = _seed_unanswered_crm_question(db)
    llm = GravitreCognitiveLLMService(app_settings=SETTINGS, org_id=ORG, user_id=USER, conversation_id=conv)
    pushed: list[Any] = []

    async def _push(frame: Any, direction: Any = FrameDirection.DOWNSTREAM) -> None:
        pushed.append(frame)

    llm.push_frame = _push  # type: ignore[method-assign]
    frame = LLMContextFrame(context=LLMContext(messages=[{"role": "user", "content": CRM_QUESTION}]))
    frame.speculation = True  # type: ignore[attr-defined]
    brain = _Brain()
    with patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=brain):
        await llm.process_frame(frame, FrameDirection.DOWNSTREAM)
    assert brain.calls == []
    assert pushed == []


@pytest.mark.asyncio
async def test_filler_never_starts_a_speculative_run(db: FakeSupabase) -> None:
    conv = _seed_unanswered_crm_question(db)
    coordinator = SpeculativeGenerationCoordinator()
    proc = SpeculativePrefetchProcessor(
        app_settings=SETTINGS,
        org_id=ORG,
        user_id=USER,
        conversation_id=conv,
        min_chars=2,
        speculative_coordinator=coordinator,
    )
    await BaseObject.setup(proc, TaskManager())

    async def _swallow(*_a: Any, **_k: Any) -> None:
        return None

    proc.push_frame = _swallow  # type: ignore[method-assign]
    proc._prefetch = _swallow  # type: ignore[method-assign]
    from pipecat.frames.frames import ProposedUserStoppedSpeakingFrame

    await proc.process_frame(
        InterimTranscriptionFrame(text="um, uh, hmm", user_id="u1", timestamp="", language=None),
        FrameDirection.DOWNSTREAM,
    )
    await proc.process_frame(ProposedUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)
    assert coordinator._run is None


def test_durable_seed_drops_only_the_trailing_unanswered_user_turns() -> None:
    drop = GravitreCognitiveLLMService._drop_trailing_unanswered_user_turns
    history = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
        {"role": "user", "content": "d"},
    ]
    assert drop(history) == history[:2]
    assert drop(history[:2]) == history[:2]
    assert drop([]) == []


@pytest.mark.parametrize(
    "text",
    ["", "  ", "...", "Uh.", "um", "Ummm", "hmm", "Hmmm...", "mm", "mhm", "mm-hmm", "uh huh", "uh-huh", "er", "ah", "oh", "a", "um, uh"],
)
def test_non_utterances(text: str) -> None:
    assert is_non_utterance(text)


@pytest.mark.parametrize(
    "text",
    ["hey", "Hi.", "yes", "no", "5", "huh?", "okay", "How many companies do we have?", "um, how many deals closed"],
)
def test_real_utterances(text: str) -> None:
    assert not is_non_utterance(text)


def test_confidence_floor_applies_to_short_transcripts_only() -> None:
    assert is_non_utterance("yeah okay", confidence=0.2)
    assert not is_non_utterance("yeah okay", confidence=0.9)
    assert not is_non_utterance("pull up the latest pipeline numbers please", confidence=0.2)
    assert average_word_confidence({"words": [{"confidence": 0.2}, {"confidence": 0.4}]}) == pytest.approx(0.3)
    assert average_word_confidence(None) is None


def test_messages_from_context_requires_a_trailing_user_turn() -> None:
    ctx = LLMContext(messages=[{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}])
    assert messages_from_context(ctx) == ("", [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}])
    ctx = LLMContext(messages=[{"role": "assistant", "content": "a"}, {"role": "user", "content": "q"}])
    assert messages_from_context(ctx) == ("q", [{"role": "assistant", "content": "a"}])


def test_gate_is_wired_ahead_of_every_transcript_reader_and_silence_is_never_answered() -> None:
    import inspect

    from app.services.pipecat_voice import pipeline as pipeline_module

    source = inspect.getsource(pipeline_module.build_pipecat_voice_task)
    listing = source[source.index("pipeline = Pipeline(") :]
    gate = listing.index("UtteranceGateProcessor(")
    assert listing.index("stt,") < gate < listing.index("TranscriptRelayProcessor(")
    assert gate < listing.index("speculative,") < listing.index("user_agg,")
    assert 'user_params_kwargs["empty_user_turn"] = None' in source
