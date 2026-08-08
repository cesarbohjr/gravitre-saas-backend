"""402 billing must not collapse into generic 502 service failure."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.tier1_voice_service import VoiceProviderError, synthesize_speech, voice_status
from app.services.voice_provider_errors import classify_upstream_http_error, error_public_payload


def _settings(**kwargs):
    base = dict(
        elevenlabs_api_key="k",
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


def test_classify_402_is_billing_not_502():
    exc = classify_upstream_http_error(
        provider="ElevenLabs",
        status_code=402,
        body_text='{"detail":{"status":"payment_required"}}',
    )
    assert exc.status_code == 402
    assert exc.error_class == "billing"
    payload = error_public_payload(exc)
    assert payload["billing_issue"] is True
    assert "billing" in payload["detail"].lower()


def test_classify_500_is_service_failure_502():
    exc = classify_upstream_http_error(provider="ElevenLabs", status_code=500, body_text="boom")
    assert exc.status_code == 502
    assert exc.error_class == "service_failure"


def test_synthesize_maps_402_upstream():
    fake_resp = MagicMock(status_code=402, text='{"detail":"quota"}')
    with patch("app.services.tier1_voice_service.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.post.return_value = fake_resp
        with pytest.raises(VoiceProviderError) as caught:
            synthesize_speech(_settings(), text="Hello")
    assert caught.value.status_code == 402
    assert caught.value.error_class == "billing"


def test_voice_status_documents_error_classes_and_entitlement_decision():
    status = voice_status(_settings())
    assert "billing" in status["error_classes"]
    assert "entitlement_decision_needed" in status
    assert status["architecture"] == "streaming_voice_session_over_unified_turn"
