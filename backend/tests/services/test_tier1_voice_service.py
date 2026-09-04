"""Tier 1 voice — provider wiring + write-confirm policy documentation."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.tier1_voice_service import (
    VoiceProviderError,
    normalize_elevenlabs_output_format,
    synthesize_speech,
    transcribe_audio,
    voice_status,
)


def _settings(**kwargs):
    base = dict(
        elevenlabs_api_key="",
        deepgram_api_key="",
        elevenlabs_tts_model="eleven_flash_v2_5",
        elevenlabs_default_voice="rachel",
        elevenlabs_voice_rachel="",
        elevenlabs_voice_adam="",
        elevenlabs_voice_josh="",
        deepgram_stt_model="nova-2",
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


@pytest.mark.parametrize(
    ("raw", "expected_fmt"),
    [
        ("mpeg", "mp3_44100_128"),
        ("mp3", "mp3_44100_128"),
        ("audio/mpeg", "mp3_44100_128"),
        (None, "mp3_44100_128"),
        ("mp3_44100_128", "mp3_44100_128"),
        ("ulaw_8000", "ulaw_8000"),
        ("mulaw", "ulaw_8000"),
    ],
)
def test_normalize_elevenlabs_output_format_never_sends_bare_mpeg(raw, expected_fmt):
    fmt, accept = normalize_elevenlabs_output_format(raw)
    assert fmt == expected_fmt
    assert fmt != "mpeg"
    if expected_fmt.startswith("ulaw"):
        assert accept == "audio/basic"
    else:
        assert accept == "audio/mpeg"


def test_synthesize_stream_uses_mp3_enum_not_bare_mpeg():
    settings = _settings(elevenlabs_api_key="k")
    stream_cm = MagicMock()
    stream_resp = MagicMock(status_code=200)
    stream_resp.iter_bytes.return_value = [b"ID3chunk"]
    stream_cm.__enter__.return_value = stream_resp
    with patch("app.services.tier1_voice_service.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.stream.return_value = stream_cm
        from app.services.tier1_voice_service import synthesize_speech_stream

        chunks = list(synthesize_speech_stream(settings, text="Hello", output_format="mpeg"))
    assert chunks == [b"ID3chunk"]
    url = client.stream.call_args.args[1]
    assert "output_format=mp3_44100_128" in url
    assert "output_format=mpeg" not in url


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
