"""Provider-level expressive voice contracts; no vendor credentials required."""
from unittest.mock import MagicMock, patch

import pytest

from app.services.pipecat_voice.tts_factory import build_live_tts_service


@pytest.mark.parametrize(
    ("tier", "stability"),
    [("light", 0.4), ("medium", 0.5), ("deep", 0.6), ("unknown", 0.5)],
)
def test_flash_provider_uses_supported_expressiveness_tier(tier, stability):
    with patch("pipecat.services.elevenlabs.tts.ElevenLabsTTSService") as service:
        service.InputParams = MagicMock(side_effect=lambda **kwargs: kwargs)
        build_live_tts_service(
            api_key="test", voice_id="test-voice", model="eleven_flash_v2_5",
            sample_rate=24000, delivery_tier=tier,
        )
        assert service.call_args.kwargs["params"]["stability"] == stability
        assert service.call_args.kwargs["params"]["style"] == 0.0


def test_flash_provider_without_tier_retains_existing_baseline():
    with patch("pipecat.services.elevenlabs.tts.ElevenLabsTTSService") as service:
        service.InputParams = MagicMock(side_effect=lambda **kwargs: kwargs)
        build_live_tts_service(
            api_key="test", voice_id="test-voice", model="eleven_flash_v2_5",
            sample_rate=24000,
        )
        assert service.call_args.kwargs["params"]["stability"] == 0.5


def test_v3_dialogue_uses_only_supported_stability_setting():
    with patch("pipecat.services.elevenlabs.dialogue.tts.ElevenLabsDialogueTTSService") as service:
        service.Settings = MagicMock(side_effect=lambda **kwargs: kwargs)
        build_live_tts_service(
            api_key="test", voice_id="test-voice", model="eleven_v3",
            sample_rate=24000, delivery_tier="light",
        )
        assert service.call_args.kwargs["settings"] == {
            "model": "eleven_v3",
            "voice": "test-voice",
            "stability": 0.5,
        }
