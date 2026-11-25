"""Use the provider protocol required by the selected synthesis model."""
from typing import Any

from app.services.tier1_voice_service import CONVERSATIONAL_VOICE_SETTINGS, voice_stability_for_tier


# Explicit supported adapter contracts; unknown models cannot silently enter the
# streaming TTS protocol. Add a model only with a matching adapter test.
_STREAM_MODELS = frozenset({"eleven_flash_v2_5", "eleven_flash_v2", "eleven_turbo_v2_5", "eleven_turbo_v2", "eleven_multilingual_v2", "eleven_monolingual_v1", "eleven_multilingual_v1"})
_DIALOGUE_MODELS = frozenset({"eleven_v3", "eleven_v3_conversational"})


def build_live_tts_service(*, api_key: str, voice_id: str, model: str, sample_rate: int, delivery_tier: str | None = None) -> Any:
    if model not in _STREAM_MODELS | _DIALOGUE_MODELS:
        raise ValueError("Unsupported live voice synthesis model")
    if model in _DIALOGUE_MODELS:
        from pipecat.services.elevenlabs.dialogue.tts import ElevenLabsDialogueTTSService

        # v3 must use Text-to-Dialogue, not the Flash Text-to-Speech socket.
        # Only stability is supported by this protocol.
        return ElevenLabsDialogueTTSService(
            api_key=api_key, sample_rate=sample_rate,
            settings=ElevenLabsDialogueTTSService.Settings(
                model=model, voice=voice_id,
                stability=float(CONVERSATIONAL_VOICE_SETTINGS["stability"]),
            ),
        )
    from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

    # Only the Flash/TTS protocol supports the full conversational settings.
    # Keep v3 Dialogue on its supported baseline stability value.
    params = dict(CONVERSATIONAL_VOICE_SETTINGS)
    if delivery_tier is not None:
        params["stability"] = voice_stability_for_tier(delivery_tier)
    return ElevenLabsTTSService(
        api_key=api_key, voice_id=voice_id, model=model, sample_rate=sample_rate,
        auto_mode=True,
        params=ElevenLabsTTSService.InputParams(**params),
    )
