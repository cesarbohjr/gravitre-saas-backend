"""Voice 3.0 retirement guardrails: do not strand saved ElevenLabs selections."""

from types import SimpleNamespace

import pytest

from app.services.tier1_voice_service import DEFAULT_VOICES, resolve_voice_id


def _settings(**overrides):
    values = {
        "elevenlabs_default_voice": "sarah",
        **{f"elevenlabs_voice_{name}": "" for name in DEFAULT_VOICES},
        **overrides,
    }
    return SimpleNamespace(**values)


@pytest.mark.parametrize("name", sorted(DEFAULT_VOICES))
def test_saved_named_voice_preserved_until_migration(name):
    key, voice_id = resolve_voice_id(_settings(), name)
    assert key == name
    assert voice_id == DEFAULT_VOICES[name]["id"]


def test_custom_voice_id_is_case_sensitive_and_not_rewritten():
    custom_id = "AbC123def456GHI789"
    assert resolve_voice_id(_settings(), custom_id) == (custom_id, custom_id)


def test_existing_custom_preset_override_is_preserved():
    custom_id = "CaseSensitiveVoice123"
    assert resolve_voice_id(
        _settings(elevenlabs_voice_sarah=custom_id), "sarah"
    ) == ("sarah", custom_id)


def test_configured_default_voice_is_respected():
    assert resolve_voice_id(_settings(elevenlabs_default_voice="josh"), None) == (
        "josh", DEFAULT_VOICES["josh"]["id"]
    )
