"""Sanitized upstream provider diagnostics must never expose response text or keys."""
import importlib.util
from pathlib import Path

from app.services.voice_provider_errors import classify_upstream_http_error

RUNNER = Path(__file__).resolve().parents[2] / "scripts" / "verify-voice-provider-roundtrip.py"
spec = importlib.util.spec_from_file_location("voice_acceptance_runner", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_elevenlabs_400_reason_is_allowlisted_and_status_is_upstream():
    error = classify_upstream_http_error(
        provider="ElevenLabs", status_code=400,
        body_text='{"detail":{"status":"invalid_api_key_prefix","message":"sensitive-token"}}',
    )
    error.acceptance_stage = "elevenlabs_tts"
    result = runner.sanitized_failure(error)
    assert result["provider"] == "elevenlabs"
    assert result["stage"] == "elevenlabs_tts"
    assert result["http_status"] == 400
    assert result["provider_reason"] == "invalid_api_key_prefix"
    assert "sensitive-token" not in str(result)


def test_unknown_provider_reason_never_echoes_arbitrary_values():
    error = classify_upstream_http_error(
        provider="ElevenLabs", status_code=400,
        body_text='{"detail":{"status":"secret-user-supplied","message":"private"}}',
    )
    result = runner.sanitized_failure(error)
    assert result["provider_reason"] == "unclassified"
    assert "private" not in str(result)
    assert "secret-user-supplied" not in str(result)
