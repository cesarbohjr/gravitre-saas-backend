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
