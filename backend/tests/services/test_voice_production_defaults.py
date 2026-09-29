from app.config import Settings
from app.services.pipecat_voice.voice_conversational_polish import (
    resolve_conversational_polish_flags,
)


def test_spoken_prompt_and_played_audio_reconciliation_are_safe_defaults():
    settings = Settings()
    flags = resolve_conversational_polish_flags(settings)
    assert flags["spoken_prompt_v2"] is True
    assert flags["played_audio_reconcile_v1"] is True
    # Prompt-only length adaptation remains opt-in because live measurements
    # showed the model could overrun the requested ceiling.
    assert flags["response_length_adapt_v1"] is False
