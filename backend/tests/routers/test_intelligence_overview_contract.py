"""Contract checks for Overview: no fabricated outcomes or unsafe execution."""
from app.routers.intelligence_overview import CAPABILITIES, ProfilePatch, _settings, DESCRIPTIONS
from pydantic import ValidationError
import pytest

def test_seven_capabilities_are_all_present():
    assert CAPABILITIES == {"contextual", "sentiment", "causal", "temporal", "relational", "adaptive", "predictive"}
    assert set(DESCRIPTIONS) == CAPABILITIES

def test_default_settings_do_not_claim_runtime_wiring():
    profile = _settings({})
    assert set(profile) == CAPABILITIES
    assert all(x["mode"] == "balanced" for x in profile.values())
    assert profile["adaptive"]["behavior_wired"] is True
    assert profile["predictive"]["behavior_wired"] is True
    assert profile["predictive"]["runtime_effect"] == "optional_evidence_presentation"

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
