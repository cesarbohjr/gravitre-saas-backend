"""Tier 1 voice — provider wiring + write-confirm policy documentation."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.tier1_voice_service import (
    VoiceProviderError,
    synthesize_speech,
    transcribe_audio,
    voice_status,
)


def _settings(**kwargs):
    base = dict(
        elevenlabs_api_key="",
        deepgram_api_key="",
        elevenlabs_tts_model="eleven_turbo_v2_5",
        elevenlabs_default_voice="rachel",
        elevenlabs_voice_rachel="",
        elevenlabs_voice_adam="",
        elevenlabs_voice_josh="",
        deepgram_stt_model="nova-2",
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_voice_status_reports_disabled_without_keys():
    status = voice_status(_settings())
    assert status["tts_enabled"] is False
    assert status["stt_enabled"] is False
    assert status["write_confirm_policy"] == "nl_yes_same_path_as_text"
    assert len(status["voices"]) == 3


def test_synthesize_requires_key():
    with pytest.raises(VoiceProviderError) as exc:
        synthesize_speech(_settings(), text="hello")
    assert exc.value.status_code == 503


def test_synthesize_calls_elevenlabs():
    settings = _settings(elevenlabs_api_key="k")
    fake_resp = MagicMock(status_code=200, content=b"ID3fake")
    with patch("app.services.tier1_voice_service.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.post.return_value = fake_resp
        audio, ctype, meta = synthesize_speech(settings, text="Hello world", voice_key="adam")
    assert audio == b"ID3fake"
    assert ctype == "audio/mpeg"
    assert meta["voice_key"] == "adam"
    assert meta["provider"] == "elevenlabs"


def test_transcribe_calls_deepgram():
    settings = _settings(deepgram_api_key="dg")
    payload = {
        "results": {
            "channels": [{"alternatives": [{"transcript": "create an apollo list named demo"}]}]
        }
    }
    fake_resp = MagicMock(status_code=200)
    fake_resp.json.return_value = payload
    with patch("app.services.tier1_voice_service.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.post.return_value = fake_resp
        text, meta = transcribe_audio(settings, audio_bytes=b"\x00\x01", content_type="audio/webm")
    assert text == "create an apollo list named demo"
    assert meta["provider"] == "deepgram"


def test_write_confirm_policy_is_not_voice_bypass():
    """Spoken yes must reuse text awaiting_confirm path — never a voice-only execute."""
    status = voice_status(_settings(elevenlabs_api_key="x", deepgram_api_key="y"))
    assert status["write_confirm_policy"] == "nl_yes_same_path_as_text"
    assert "bypass" in status["write_confirm_note"].lower()
