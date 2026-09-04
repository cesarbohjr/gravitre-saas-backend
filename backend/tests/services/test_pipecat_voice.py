"""Unit tests for Pipecat voice bridge helpers (no live Deepgram/ElevenLabs)."""
from __future__ import annotations

import asyncio
import base64
import json

import pytest

from app.services.pipecat_voice.cognitive_llm import _messages_from_context
from app.services.pipecat_voice.json_audio_serializer import GravitreJsonAudioSerializer


class _Ctx:
    def __init__(self, messages):
        self._messages = messages

    def get_messages(self):
        return self._messages


def test_messages_from_context_extracts_latest_user():
    ctx = _Ctx(
        [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
            {"role": "user", "content": "what's our pipeline?"},
        ]
    )
    user_text, history = _messages_from_context(ctx)
    assert user_text == "what's our pipeline?"
    assert history == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]


def test_messages_from_context_multipart_content():
    ctx = _Ctx(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "part a"},
                    {"type": "text", "text": "part b"},
                ],
            }
        ]
    )
    user_text, history = _messages_from_context(ctx)
    assert user_text == "part a part b"
    assert history == []


@pytest.mark.asyncio
async def test_json_serializer_roundtrip_audio_and_text():
    ser = GravitreJsonAudioSerializer()
    pcm = b"\x00\x01" * 8
    from pipecat.frames.frames import OutputAudioRawFrame

    out = await ser.serialize(
        OutputAudioRawFrame(audio=pcm, sample_rate=16000, num_channels=1)
    )
    assert out is not None
    msg = json.loads(out)
    assert msg["type"] == "audio"
    assert base64.b64decode(msg["pcm16_b64"]) == pcm

    frame = await ser.deserialize(
        json.dumps({"type": "audio", "pcm16_b64": base64.b64encode(pcm).decode(), "sample_rate": 16000})
    )
    assert frame is not None
    assert frame.audio == pcm

    text_frame = await ser.deserialize(json.dumps({"type": "text", "text": "say hi"}))
    assert text_frame is not None
    assert text_frame.text == "say hi"
    assert getattr(text_frame, "finalized", False) is True

    interrupt = await ser.deserialize(json.dumps({"type": "interrupt"}))
    assert interrupt is not None
    assert interrupt.__class__.__name__ == "InterruptionFrame"


def test_voice_status_exposes_pipecat_fields():
    from app.services.tier1_voice_service import voice_status

    class S:
        elevenlabs_api_key = ""
        deepgram_api_key = ""
        elevenlabs_default_voice = "rachel"
        elevenlabs_tts_model = "eleven_flash_v2_5"
        elevenlabs_voice_rachel = ""
        elevenlabs_voice_adam = ""
        elevenlabs_voice_josh = ""
        voice_pipecat_enabled = False

    status = voice_status(S())  # type: ignore[arg-type]
    assert status["pipecat_enabled"] is False
    assert status["pipecat_ws_path"] == "/api/voice/pipecat/ws"
    assert status["default_orchestration"] == "http_session_turn"
    assert status["pipecat_ws_clients_accepted"] is False
    assert "pipecat_available" in status


@pytest.mark.asyncio
async def test_text_turn_kick_emits_bookends():
    from pipecat.frames.frames import TranscriptionFrame, UserStartedSpeakingFrame, UserStoppedSpeakingFrame

    from app.services.pipecat_voice.text_turn_kick import TextTurnKickProcessor

    pushed: list = []
    kick = TextTurnKickProcessor()

    async def _capture(frame, direction=None):
        pushed.append(frame)

    kick.push_frame = _capture  # type: ignore[method-assign]
    # FrameProcessor.process_frame expects setup; call our override path directly.
    frame = TranscriptionFrame(text="hi", user_id="browser", timestamp="", finalized=True)
    await kick.process_frame(frame, None)  # type: ignore[arg-type]
    # super().process_frame may fail without full setup — if so, call logic inline:
    if not pushed:
        await TextTurnKickProcessor.process_frame(kick, frame, None)  # type: ignore[arg-type]
    kinds = [type(f).__name__ for f in pushed]
    assert "UserStartedSpeakingFrame" in kinds or isinstance(pushed[0], UserStartedSpeakingFrame)
    assert any(isinstance(f, TranscriptionFrame) for f in pushed)
    assert any(isinstance(f, UserStoppedSpeakingFrame) for f in pushed)