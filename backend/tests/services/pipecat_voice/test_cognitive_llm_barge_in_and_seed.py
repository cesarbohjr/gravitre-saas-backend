"""Behavioural coverage for the voice turn after a barge-in, and for speculative seeding.

Uses the real GravitreCognitiveLLMService, ElevenLabsInterruptReporter and
SpeculativePrefetchProcessor against ``FakeSupabase`` (filters honoured).
"""
from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pipecat.frames.frames import (
    InterimTranscriptionFrame,
    InterruptionFrame,
    LLMFullResponseStartFrame,
    OutputTransportMessageUrgentFrame,
    ProposedUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services import chat_turn_cancel_service
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
from app.services.pipecat_voice.interrupt_reporter import ElevenLabsInterruptReporter
from app.services.pipecat_voice.speculative_generation import SpeculativeGenerationCoordinator
from app.services.pipecat_voice.speculative_prefetch import SpeculativePrefetchProcessor
from tests.support.fake_supabase import FakeQuery, FakeSupabase

ORG = "00000000-0000-4000-8000-0000000000a1"
USER = "00000000-0000-4000-8000-0000000000c3"
SETTINGS = SimpleNamespace()


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeSupabase:
    client = FakeSupabase()
    monkeypatch.setattr("app.workflows.repository.get_supabase_client", lambda _s: client)
    monkeypatch.setattr("app.routers.assistant.get_supabase_client", lambda _s: client)
    monkeypatch.setattr(chat_turn_cancel_service, "get_redis_client", lambda _s=None: None)
    monkeypatch.setattr("app.routers.assistant._remember_completed_turn", lambda **_k: None)
    chat_turn_cancel_service._local_stops.clear()
    return client


def _seed_history(db: FakeSupabase) -> str:
    conv = db.seed_conversation(org_id=ORG, user_id=USER)
    db.rows("conversations", id=conv)[0]["last_summary"] = "Budget is $12k; paid social excluded."
    db.tables.setdefault("conversation_messages", []).extend(
        [
            {"id": "m1", "conversation_id": conv, "role": "user", "content": "Priority account is Acme.", "created_at": "2026-10-05T10:00:00Z"},
            {"id": "m2", "conversation_id": conv, "role": "assistant", "content": "Noted: Acme first.", "created_at": "2026-10-05T10:00:01Z"},
        ]
    )
    return conv


class _Context:
    def __init__(self, text: str) -> None:
        self._text = text

    def get_messages(self) -> list[dict[str, Any]]:
        return [{"role": "user", "content": self._text}]


def _intelligence(calls: list[dict[str, Any]], reply: str = "Here is the pilot part."):
    async def _stream(**kwargs: Any):
        calls.append(kwargs)
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": reply})
        yield AssistantStreamComplete(full_content=reply, tool_results=[], react_result=None, model="test")

    return type("FakeIntelligence", (), {"execute_task_streaming": staticmethod(_stream)})()


@pytest.mark.asyncio
async def test_turn_after_a_barge_in_is_answered(db: FakeSupabase) -> None:
    conv = _seed_history(db)
    llm = GravitreCognitiveLLMService(app_settings=SETTINGS, org_id=ORG, user_id=USER, conversation_id=conv)
    llm.push_frame = AsyncMock()
    llm._push_llm_text = AsyncMock()
    reporter = ElevenLabsInterruptReporter(
        reconcile_played_audio_enabled=True, settings=SETTINGS, org_id=ORG, user_id=USER, conversation_id=conv
    )
    await BaseObject.setup(reporter, TaskManager())
    reporter.push_frame = AsyncMock()  # type: ignore[method-assign]
    llm._interrupt_reporter = reporter

    # The previous answer is cut off mid-sentence.
    reporter.begin_turn("Walk me through the rollout plan")
    await reporter.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await reporter.process_frame(
        OutputTransportMessageUrgentFrame(message={"type": "assistant_text", "delta": "The rollout starts Monday."}),
        FrameDirection.DOWNSTREAM,
    )
    await reporter.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)

    calls: list[dict[str, Any]] = []
    with patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=_intelligence(calls)):
        await llm._run_gravitre_turn(_Context("Actually, just the pilot part"))

    assert len(calls) == 1, "the turn after a barge-in was skipped as if the user had pressed stop"
    assert calls[0]["query"] == "Actually, just the pilot part"
    assert not chat_turn_cancel_service.is_stop_requested(ORG, conv, settings=SETTINGS)


@pytest.mark.asyncio
async def test_speculative_run_is_seeded_from_durable_history_off_the_loop(db: FakeSupabase) -> None:
    conv = _seed_history(db)
    loop_thread = threading.get_ident()
    reads_on_loop: list[str] = []

    def _record(query: FakeQuery) -> None:
        if threading.get_ident() == loop_thread:
            reads_on_loop.append(query.table)

    db.hooks.append(_record)

    llm = GravitreCognitiveLLMService(app_settings=SETTINGS, org_id=ORG, user_id=USER, conversation_id=conv)
    coordinator = SpeculativeGenerationCoordinator()
    proc = SpeculativePrefetchProcessor(
        app_settings=SETTINGS,
        org_id=ORG,
        user_id=USER,
        agent={"id": "agent-1"},
        conversation_id=conv,
        min_chars=5,
        speculative_coordinator=coordinator,
        durable_context_provider=llm.speculative_durable_context,
    )
    await BaseObject.setup(proc, TaskManager())
    proc.push_frame = AsyncMock()
    proc._prefetch = AsyncMock()

    calls: list[dict[str, Any]] = []
    await proc.process_frame(
        InterimTranscriptionFrame(text="which account is the priority", user_id="u1", timestamp="", language=None),
        FrameDirection.DOWNSTREAM,
    )
    with patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=_intelligence(calls)):
        await proc.process_frame(ProposedUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)
        events = [event async for event in coordinator._run.events()]  # noqa: SLF001

    assert events, "speculative run produced nothing"
    assert len(calls) == 1
    history = calls[0]["conversation_history"]
    assert [m["content"] for m in history] == ["Priority account is Acme.", "Noted: Acme first."]
    assert calls[0]["history_summary"] == "Budget is $12k; paid social excluded."
    assert calls[0]["conversation_id"] == conv
    assert reads_on_loop == [], f"durable seed loaded on the event loop: {reads_on_loop}"


@pytest.mark.asyncio
async def test_speculative_and_confirmed_turn_share_one_durable_load(db: FakeSupabase) -> None:
    conv = _seed_history(db)
    llm = GravitreCognitiveLLMService(app_settings=SETTINGS, org_id=ORG, user_id=USER, conversation_id=conv)

    await asyncio.gather(llm.speculative_durable_context(), llm._ensure_durable_context())

    message_reads = [entry for entry in db.log if entry[0] == "select" and entry[1] == "conversation_messages"]
    assert len(message_reads) == 1
