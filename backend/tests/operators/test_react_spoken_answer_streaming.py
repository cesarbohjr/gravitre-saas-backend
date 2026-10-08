"""Spoken ReAct answers stream sentence by sentence (stream_answer=True).

The ReAct model call was non-streamed, so a spoken turn's first audio waited
for the whole generation. With stream_answer the round before any tool runs is
streamed (the unified LIVE streaming completion) and each complete sentence is
yielded while the model is still generating. A tool round, the
NEEDS_HUMAN_INPUT marker and text chat (stream_answer=False) keep the old path.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.operators.react_engine import ReActEngine, ReActStatus, _SpokenAnswerStream
from app.services.tool_types import ToolContext


def _settings() -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
    )


def _chunk(content: str | None = None, tool_call: dict | None = None):
    tool_calls = None
    if tool_call is not None:
        tool_calls = [
            SimpleNamespace(
                index=0,
                id=tool_call.get("id"),
                function=SimpleNamespace(name=tool_call.get("name"), arguments=tool_call.get("arguments")),
            )
        ]
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content, tool_calls=tool_calls))],
        usage=None,
    )


class _ScriptedStream:
    """Yields scripted chunks; ``gate`` holds the stream mid-generation."""

    def __init__(self, chunks: list, gate: asyncio.Event | None = None, hold_after: int = 1) -> None:
        self.chunks = chunks
        self.gate = gate
        self.hold_after = hold_after

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for i, chunk in enumerate(self.chunks):
            if self.gate is not None and i == self.hold_after:
                await self.gate.wait()
            yield chunk


class _FakeOpenAI:
    def __init__(self, streams: list[_ScriptedStream]) -> None:
        self.streams = list(streams)
        self.calls: list[dict] = []

        async def create(**kwargs):
            self.calls.append(kwargs)
            assert kwargs.get("stream") is True
            return self.streams.pop(0)

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


def _engine(fake: _FakeOpenAI) -> ReActEngine:
    engine = ReActEngine(settings=_settings(), registry=MagicMock())
    engine.registry.get_available_tools = AsyncMock(
        return_value=[{"type": "function", "function": {"name": "web_search", "parameters": {}}}]
    )
    engine.registry.list_connected_integrations = MagicMock(return_value=["platform"])
    engine.registry.execute_tool = AsyncMock(
        return_value={"success": True, "tool": "web_search", "results": [], "totalResults": 0, "query": "q"}
    )
    engine.router = SimpleNamespace(_openai=fake, settings=_settings())
    return engine


def _ctx() -> ToolContext:
    return ToolContext(settings=_settings(), client=MagicMock(), org_id="org-1", actor_id="user-1")


async def _run(engine: ReActEngine, *, stream_answer: bool, on_event=None):
    events = []
    with patch("app.operators.react_engine.moderate_input", AsyncMock()), patch(
        "app.operators.react_engine.write_audit_event", MagicMock()
    ):
        async for event in engine.run_streaming(
            ctx=_ctx(),
            task="what should i focus on today",
            system_prompt="sys",
            permitted_tools=["web_search"],
            connected_integrations=["platform"],
            max_iterations=3,
            model="gpt-4o-mini",
            stream_answer=stream_answer,
        ):
            events.append(event)
            if on_event is not None:
                on_event(event)
    return events


@pytest.mark.asyncio
async def test_first_sentence_is_yielded_before_generation_completes() -> None:
    gate = asyncio.Event()
    stream = _ScriptedStream(
        [_chunk("Start with Acme"), _chunk(" today. "), _chunk("Then review "), _chunk("Northwind.")],
        gate=gate,
        hold_after=2,
    )
    engine = _engine(_FakeOpenAI([stream]))
    seen_before_release: list[str] = []

    def on_event(event) -> None:
        if event.kind == "text_delta" and not gate.is_set():
            seen_before_release.append(event.content)
            # Generation is still held; releasing it lets the turn finish.
            gate.set()

    events = await asyncio.wait_for(_run(engine, stream_answer=True, on_event=on_event), timeout=5)
    assert seen_before_release == ["Start with Acme today. "]
    text = "".join(e.content for e in events if e.kind == "text_delta")
    assert text == "Start with Acme today. Then review Northwind."
    done = [e for e in events if e.kind == "done"][-1]
    assert done.react_result.status == ReActStatus.COMPLETED
    assert done.react_result.answer == "Start with Acme today. Then review Northwind."


@pytest.mark.asyncio
async def test_tool_round_text_is_not_released_and_tools_still_run() -> None:
    first = _ScriptedStream(
        [
            _chunk(tool_call={"id": "tc1", "name": "web_search", "arguments": '{"query":"q"}'}),
            _chunk("Checking that now. "),
        ]
    )
    engine = _engine(_FakeOpenAI([first]))
    final = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Here is what I found.", tool_calls=[]))]
    )
    with patch.object(engine, "_chat_with_tools", AsyncMock(return_value=final)) as non_streamed:
        events = await _run(engine, stream_answer=True)
    kinds = [e.kind for e in events]
    assert "tool_start" in kinds and "tool_complete" in kinds
    texts = [e.content for e in events if e.kind == "text_delta"]
    assert "Checking that now. " not in texts
    # Rounds after a tool ran keep the non-streamed call.
    non_streamed.assert_awaited_once()
    assert "".join(texts) == "Here is what I found."


@pytest.mark.asyncio
async def test_needs_human_marker_is_never_streamed() -> None:
    stream = _ScriptedStream([_chunk("NEEDS_HUMAN_INPUT: "), _chunk("Which account do you mean? ")])
    engine = _engine(_FakeOpenAI([stream]))
    events = await _run(engine, stream_answer=True)
    text = "".join(e.content for e in events if e.kind == "text_delta")
    assert "NEEDS_HUMAN_INPUT" not in text
    assert text == "Which account do you mean?"
    assert events[-1].react_result.status == ReActStatus.NEEDS_HUMAN_INPUT


@pytest.mark.asyncio
async def test_text_chat_keeps_the_non_streamed_call() -> None:
    fake = _FakeOpenAI([])
    engine = _engine(fake)
    final = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Plain answer.", tool_calls=[]))]
    )
    with patch.object(engine, "_chat_with_tools", AsyncMock(return_value=final)):
        events = await _run(engine, stream_answer=False)
    assert fake.calls == []
    assert "".join(e.content for e in events if e.kind == "text_delta") == "Plain answer."


@pytest.mark.asyncio
async def test_stream_failure_ends_the_turn_like_a_failed_call() -> None:
    fake = _FakeOpenAI([])

    async def boom(**_kwargs):
        raise RuntimeError("provider down")

    fake.chat.completions.create = boom
    engine = _engine(fake)
    events = await asyncio.wait_for(_run(engine, stream_answer=True), timeout=5)
    assert events[-1].kind == "done"
    assert events[-1].react_result.status == ReActStatus.ERROR


def test_answer_stream_holds_partial_sentences_and_stops_on_tool_delta() -> None:
    stream = _SpokenAnswerStream()
    stream.feed("Hello there")
    assert stream.released == ""
    stream.feed(". How are")
    assert stream.released == "Hello there. "
    stream.tool_round()
    stream.feed(" you? Fine. ")
    assert stream.released == "Hello there. "
