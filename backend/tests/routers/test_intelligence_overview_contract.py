"""Contract checks for Overview: no fabricated outcomes or unsafe execution."""
from app.routers.intelligence_overview import CAPABILITIES, ProfilePatch, _settings, DESCRIPTIONS
from pydantic import ValidationError
import pytest

def test_seven_capabilities_are_all_present():
    assert CAPABILITIES == {"contextual", "sentiment", "causal", "temporal", "relational", "adaptive", "predictive"}
    assert set(DESCRIPTIONS) == CAPABILITIES

def test_default_settings_report_current_runtime_policy_contract():
    profile = _settings({})
    assert set(profile) == CAPABILITIES
    assert all(x["mode"] == "balanced" for x in profile.values())
    assert profile["adaptive"]["behavior_wired"] is True
    assert profile["predictive"]["behavior_wired"] is True
    assert profile["predictive"]["runtime_effect"] == "optional_enrichment_eligibility_and_evidence_threshold"
    assert profile["adaptive"]["runtime_effect"] == "optional_enrichment_eligibility_guidance_and_evidence_threshold"

def test_profile_validates_mode():
    with pytest.raises(ValidationError):
        ProfilePatch(capabilities={"predictive": {"mode": "aggressive"}})

def test_unknown_capability_not_silently_in_default():
    profile = _settings({"invented": {"mode": "proactive"}, "predictive": {"mode": "conservative"}})
    assert "invented" not in profile
    assert profile["predictive"]["mode"] == "conservative"

def test_profile_rejects_arbitrary_extra_control_fields():
    with pytest.raises(ValidationError):
        ProfilePatch(capabilities={"sentiment": {"mode": "balanced", "automate": True}})


def test_safe_abilities_report_their_switch_and_others_stay_on():
    profile = _settings({"sentiment": {"mode": "balanced", "enabled": False}, "temporal": {"mode": "balanced", "enabled": False}})
    assert profile["sentiment"]["enabled"] is False
    assert profile["sentiment"]["can_turn_off"] is True
    # Time can't be turned off, so a stored False is ignored.
    assert profile["temporal"]["enabled"] is True
    assert profile["temporal"]["can_turn_off"] is False
    assert {k for k, v in _settings({}).items() if v["can_turn_off"]} == {"sentiment", "causal", "predictive", "adaptive"}


def test_turning_off_an_always_on_ability_is_refused():
    from unittest.mock import MagicMock, patch
    from fastapi import HTTPException
    from app.routers.intelligence_overview import update_profile

    body = ProfilePatch(capabilities={"contextual": {"mode": "balanced", "enabled": False}})
    with patch("app.routers.intelligence_overview._db") as db:
        with pytest.raises(HTTPException) as exc:
            update_profile(body, "org-1", ({"id": "u"}, {}), MagicMock())
    assert exc.value.status_code == 422
    db.assert_not_called()
