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
    def __init__(self, deltas: list[str]) -> None:
        self._deltas = deltas

    async def execute_task_streaming(self, **_: Any) -> AsyncIterator[Any]:
        for delta in self._deltas:
            yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": delta})
        yield AssistantStreamComplete(
            full_content="".join(self._deltas),
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
