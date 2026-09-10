"""Regression tests for voice session streaming behavior."""
from __future__ import annotations

import base64
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services import voice_session_service
from app.services.tier1_voice_service import VoiceProviderError


class _FakeIntelligence:
    def __init__(self, deltas: list[str], complete: str | None = None) -> None:
        self._deltas = deltas
        self._complete = complete if complete is not None else "".join(deltas)
        self.kwargs: dict[str, Any] = {}

    async def execute_task_streaming(self, **kwargs: Any) -> AsyncIterator[Any]:
        self.kwargs = dict(kwargs)
        for delta in self._deltas:
            yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": delta})
        yield AssistantStreamComplete(
            full_content=self._complete,
            tool_results=[],
            react_result=None,
            model="gpt-test",
            message_id="msg-voice-1",
        )


def _settings_with_voice(mock_settings):
    mock_settings.elevenlabs_api_key = "test-elevenlabs"
    return mock_settings


@pytest.mark.asyncio
async def test_stream_voice_turn_coalesces_streamed_audio_chunks(monkeypatch, mock_settings):
    monkeypatch.setattr(
        "app.operators.agent_intelligence.get_agent_intelligence",
        lambda: _FakeIntelligence(["Please provide recipient, subject, and body."]),
    )

    def _fake_tts_stream(*_: Any, **__: Any) -> Iterator[bytes]:
        yield b"chunk-1-"
        yield b"chunk-2"

    monkeypatch.setattr(voice_session_service, "synthesize_speech_stream", _fake_tts_stream)

    events = [
        event
        async for event in voice_session_service.stream_voice_turn_events(
            settings=_settings_with_voice(mock_settings),
            org_id="org-1",
            user_id="user-1",
            text="Send an email",
            agent={"id": "agent-1"},
            conversation_id="conv-1",
        )
    ]

    audio_events = [e for e in events if e.get("type") == "voice.audio.delta"]
    assert len(audio_events) == 1
    assert base64.b64decode(str(audio_events[0]["audio_base64"])) == b"chunk-1-chunk-2"
    assert any(e.get("type") == "voice.turn.complete" for e in events)


@pytest.mark.asyncio
async def test_stream_voice_turn_keeps_text_path_when_tts_fails(monkeypatch, mock_settings):
    monkeypatch.setattr(
        "app.operators.agent_intelligence.get_agent_intelligence",
        lambda: _FakeIntelligence(["What's the recipient, subject, and body?"]),
    )

    def _failing_tts_stream(*_: Any, **__: Any) -> Iterator[bytes]:
        raise VoiceProviderError(
            "ElevenLabs timeout",
            status_code=504,
            error_class="service_failure",
            provider="elevenlabs",
        )
        yield b""  # pragma: no cover

    monkeypatch.setattr(voice_session_service, "synthesize_speech_stream", _failing_tts_stream)

    events = [
        event
        async for event in voice_session_service.stream_voice_turn_events(
            settings=_settings_with_voice(mock_settings),
            org_id="org-1",
            user_id="user-1",
            text="Send an email",
            agent={"id": "agent-1"},
            conversation_id="conv-1",
        )
    ]

    complete = next((e for e in events if e.get("type") == "voice.turn.complete"), None)
    assert complete is not None
    assert "recipient, subject, and body" in str(complete.get("text") or "").lower()

    errors = [e for e in events if e.get("type") == "voice.error"]
    assert errors
    assert errors[0].get("provider") == "elevenlabs"


@pytest.mark.asyncio
async def test_voice_session_uses_agent_mode_for_google_ads(monkeypatch, mock_settings):
    fake = _FakeIntelligence(["I planned a 5-step orchestration."])
    monkeypatch.setattr(
        "app.operators.agent_intelligence.get_agent_intelligence",
        lambda: fake,
    )
    monkeypatch.setattr(
        voice_session_service,
        "synthesize_speech_stream",
        lambda *_, **__: iter((b"x",)),
    )
    events = [
        event
        async for event in voice_session_service.stream_voice_turn_events(
            settings=_settings_with_voice(mock_settings),
            org_id="org-1",
            user_id="user-1",
            text=(
                "I have a Google Ads campaign strategy ready to go live. "
                "Don't execute anything without my approval first."
            ),
            agent={"id": "agent-1"},
            conversation_id="conv-1",
        )
    ]
    assert fake.kwargs.get("mode") == "agent"
    assert fake.kwargs.get("spoken_mode") is True
    assert any(e.get("type") == "voice.turn.complete" for e in events)


@pytest.mark.asyncio
async def test_voice_session_prefers_complete_payload_over_streamed_deltas(
    monkeypatch, mock_settings
):
    fake = _FakeIntelligence(
        ["I don't have enough information yet to do that safely."],
        complete="I planned a **5-step orchestration**, but **nothing is runnable**.",
    )
    monkeypatch.setattr(
        "app.operators.agent_intelligence.get_agent_intelligence",
        lambda: fake,
    )
    monkeypatch.setattr(
        voice_session_service,
        "synthesize_speech_stream",
        lambda *_, **__: iter((b"x",)),
    )
    events = [
        event
        async for event in voice_session_service.stream_voice_turn_events(
            settings=_settings_with_voice(mock_settings),
            org_id="org-1",
            user_id="user-1",
            text="hey",
            agent={"id": "agent-1"},
            conversation_id="conv-1",
        )
    ]
    complete = next((e for e in events if e.get("type") == "voice.turn.complete"), None)
    assert complete is not None
    assert "5-step orchestration" in str(complete.get("text") or "")
    assert "enough information" not in str(complete.get("text") or "").lower()
