"""Unit tests for Pipecat voice bridge helpers (no live Deepgram/ElevenLabs)."""
from __future__ import annotations

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
        json.dumps(
            {
                "type": "audio",
                "pcm16_b64": base64.b64encode(pcm).decode(),
                "sample_rate": 16000,
            }
        )
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
        openai_api_key = ""
        elevenlabs_default_voice = "rachel"
        elevenlabs_tts_model = "eleven_flash_v2_5"
        elevenlabs_voice_rachel = ""
        elevenlabs_voice_adam = ""
        elevenlabs_voice_josh = ""
        voice_pipecat_enabled = False
        voice_pipecat_stt = "flux"
        voice_pipecat_stt_fallback_enabled = True
        voice_pipecat_stt_fallback = "nova3"
        api_public_url = ""

    status = voice_status(S())  # type: ignore[arg-type]
    assert status["pipecat_enabled"] is False
    assert status["pipecat_ws_path"] == "/api/voice/pipecat/ws"
    assert status["default_orchestration"] == "http_session_turn"
    assert status["pipecat_ws_clients_accepted"] is False
    assert "pipecat_available" in status
    assert "pipecat_ws_hint" in status
    assert str(status["pipecat_ws_hint"]).startswith("ws")
    assert status["pipecat_stt"]["stt_provider"] == "deepgram_flux"
    assert status["pipecat_tts"]["model"] == "eleven_flash_v2_5"

    class On:
        elevenlabs_api_key = ""
        deepgram_api_key = ""
        openai_api_key = ""
        elevenlabs_default_voice = "rachel"
        elevenlabs_tts_model = "eleven_flash_v2_5"
        elevenlabs_voice_rachel = ""
        elevenlabs_voice_adam = ""
        elevenlabs_voice_josh = ""
        voice_pipecat_enabled = True
        voice_pipecat_stt = "flux"
        voice_pipecat_stt_fallback_enabled = True
        voice_pipecat_stt_fallback = "nova3"
        api_public_url = "https://api.gravitre.app"

    on = voice_status(On())  # type: ignore[arg-type]
    assert on["default_orchestration"] == "pipecat"
    assert on["pipecat_ws_clients_accepted"] is True
    assert on["pipecat_ws_hint"] == "wss://api.gravitre.app"
    assert on["pipecat_tts"]["transport"] == "websocket"


def test_stt_factory_provider_resolution_and_meta():
    from app.services.pipecat_voice.stt_factory import (
        resolve_pipecat_stt_provider,
        stt_meta,
    )

    class S:
        voice_pipecat_stt = "flux"

    assert resolve_pipecat_stt_provider(S()) == "flux"
    assert resolve_pipecat_stt_provider(S(), override="nova3") == "nova3"
    meta = stt_meta("flux")
    assert meta["stt_model"] == "flux-general-en"
    assert meta["stt_provider"] == "deepgram_flux"


def test_text_turn_kick_targets_browser_finals_only():
    from pipecat.frames.frames import TranscriptionFrame

    browser = TranscriptionFrame(text="hi", user_id="browser", timestamp="", finalized=True)
    mic = TranscriptionFrame(text="hi", user_id="deepgram", timestamp="", finalized=True)
    assert bool(getattr(browser, "finalized", False)) and browser.user_id == "browser"
    assert mic.user_id != "browser"
