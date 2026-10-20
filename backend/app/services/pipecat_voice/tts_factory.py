"""Use the provider protocol required by the selected synthesis model."""
from typing import Any

from app.services.tier1_voice_service import CONVERSATIONAL_VOICE_SETTINGS


def build_live_tts_service(*, api_key: str, voice_id: str, model: str, sample_rate: int) -> Any:
    if model.startswith("eleven_v3"):
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

    return ElevenLabsTTSService(
        api_key=api_key, voice_id=voice_id, model=model, sample_rate=sample_rate,
        auto_mode=True,
        params=ElevenLabsTTSService.InputParams(**CONVERSATIONAL_VOICE_SETTINGS),
    )
