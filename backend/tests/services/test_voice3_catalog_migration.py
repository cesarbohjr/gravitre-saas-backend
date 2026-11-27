"""Voice 3.0 discovery migration must not rewrite saved voice selections."""
from types import SimpleNamespace
from unittest.mock import patch

from app.services.tier1_voice_service import DEFAULT_VOICES, resolve_voice_id
from app.services.voice_library_service import list_voice_library, recommend_voices_for_agent


def _settings(approved=""):
    return SimpleNamespace(
        voice_3_approved_voice_ids=approved,
        elevenlabs_default_voice="sarah",
        **{f"elevenlabs_voice_{name}": "" for name in DEFAULT_VOICES},
    )


def _catalog():
    return [
        {"voice_id": "ApprovedCaseSensitive123", "name": "Approved", "categories": ["general"]},
        {"voice_id": "approvedcasesensitive123", "name": "Different", "categories": ["general"]},
        {"voice_id": DEFAULT_VOICES["sarah"]["id"], "name": "Sarah", "categories": ["general"]},
    ]


def test_approved_catalog_filters_discovery_and_recommendations_without_rewriting_saved_voice():
    settings = _settings(" ApprovedCaseSensitive123, ApprovedCaseSensitive123 ")
    with patch("app.services.voice_library_service.fetch_elevenlabs_shared_voices", return_value=_catalog()):
        assert [v["name"] for v in list_voice_library(settings)["voices"]] == ["Approved"]
        assert [v["name"] for v in recommend_voices_for_agent(settings)] == ["Approved"]
    assert resolve_voice_id(settings, "sarah") == ("sarah", DEFAULT_VOICES["sarah"]["id"])


def test_unconfigured_catalog_preserves_existing_discovery():
    with patch("app.services.voice_library_service.fetch_elevenlabs_shared_voices", return_value=_catalog()):
        assert list_voice_library(_settings())["count"] == 3


def test_configured_missing_voice_does_not_reintroduce_legacy_choices():
    with patch("app.services.voice_library_service.fetch_elevenlabs_shared_voices", return_value=_catalog()):
        assert list_voice_library(_settings("MissingApprovedVoice123"))["voices"] == []


def test_effective_identity_precedence_and_discovery_independence():
    from app.services.voice_agent_profile import resolve_effective_voice

    settings = _settings("ApprovedCaseSensitive123")
    settings.elevenlabs_voice_sarah = "OverrideCaseSensitive123"
    settings.elevenlabs_default_voice = "adam"
    custom = {"voice_source": "custom_voice_v3", "voice_id": "CustomShort",
              "voice_key": "sarah", "unknown": {"preserve": True}}
    before = dict(custom)
    cases = [
        ({"voice_profile": custom}, "rachel", "CustomShort", "agent_id"),
        ({"voice_profile": {"voice_id": "LegacyCaseSensitive123", "voice_key": "adam"}},
         "rachel", "LegacyCaseSensitive123", "agent_id"),
        ({"voiceProfile": {"voice_id": "CamelCaseCustom"}}, None, "CamelCaseCustom", "agent_id"),
        ({"voice_profile": {"voice_key": " SARAH "}}, "rachel", "OverrideCaseSensitive123", "agent_key"),
        ({}, "rachel", DEFAULT_VOICES["rachel"]["id"], "request"),
        (None, None, DEFAULT_VOICES["adam"]["id"], "default"),
    ]
    for agent, request, expected, origin in cases:
        result = resolve_effective_voice(settings, agent, request)
        assert result["voice_id"] == expected
        assert result["resolution"] == origin
    assert resolve_effective_voice(settings, {"voice_profile": custom})["voice_source"] == "custom_voice_v3"
    assert custom == before


def test_pipecat_uses_effective_identity_without_activating_v3():
    from app.services.pipecat_voice.pipeline import resolve_voice_and_tts_model

    settings = _settings()
    settings.elevenlabs_tts_model = "eleven_v3"
    agent = {"voiceProfile": {"voice_id": "CustomShort", "voice_key": "adam"}}
    assert resolve_voice_and_tts_model(settings, agent=agent, voice_key="sarah") == (
        "CustomShort", "eleven_flash_v2_5")
