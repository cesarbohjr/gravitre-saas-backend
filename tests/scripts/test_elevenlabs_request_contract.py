"""Regression tests for ElevenLabs voice selection and request serialization."""
from types import SimpleNamespace

import httpx

from app.services.tier1_voice_service import resolve_voice_id, synthesize_speech


def _settings():
    return SimpleNamespace(
        elevenlabs_api_key="test-key",
        elevenlabs_default_voice="sarah",
        elevenlabs_tts_model="eleven_flash_v2_5",
        elevenlabs_voice_sarah="",
        elevenlabs_voice_rachel="",
        elevenlabs_voice_adam="",
        elevenlabs_voice_josh="",
        elevenlabs_voice_eric="",
    )


def test_raw_voice_id_preserves_case():
    raw_id = "AbCdEFghIJklMNop1234"
    assert resolve_voice_id(_settings(), raw_id) == (raw_id, raw_id)


def test_alias_is_case_insensitive():
    key, voice_id = resolve_voice_id(_settings(), "SARAH")
    assert key == "sarah"
    assert voice_id == "EXAVITQu4vr4xnSDxMaL"


def test_elevenlabs_batch_payload_and_case_sensitive_voice_id():
    raw_id = "AbCdEFghIJklMNop1234"
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=b"fake-mp3", headers={"content-type": "audio/mpeg"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        audio, mime, meta = synthesize_speech(
            _settings(), text="Hello.", voice_key=raw_id,
            expression_tier="medium", http_client=client,
        )
    assert audio == b"fake-mp3"
    assert mime == "audio/mpeg"
    assert meta["voice_id"] == raw_id
    assert f"/text-to-speech/{raw_id}" in str(seen[0].url)
    assert seen[0].url.params["output_format"] == "mp3_44100_128"
    assert seen[0].headers["Accept"] == "audio/mpeg"
    import json
    payload = json.loads(seen[0].content)
    assert payload["model_id"] == "eleven_flash_v2_5"
    assert payload["voice_settings"]["stability"] == 0.5
    assert payload["voice_settings"]["similarity_boost"] == 0.75
    assert payload["voice_settings"]["style"] == 0.0
    assert payload["voice_settings"]["use_speaker_boost"] is True
