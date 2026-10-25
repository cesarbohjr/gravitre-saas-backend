"""Sensitivity policy must never grant execution or fabricate intelligence."""
from app.services.intelligence_overview_policy import (
    normalize_policy, include_optional_evidence,
)

def test_policy_defaults_for_missing_or_unexpected_modes():
    assert normalize_policy(None)["adaptive"] == "balanced"
    assert normalize_policy({"predictive": {"mode": "aggressive"}})["predictive"] == "balanced"

def test_conservative_adaptive_is_persistently_selectable():
    profile = normalize_policy({"adaptive": {"mode": "conservative"}})
    assert profile["adaptive"] == "conservative"

def test_unrequested_causal_and_predictive_are_not_triggered_by_proactive():
    assert not include_optional_evidence("causal", "proactive", {})
    assert not include_optional_evidence("predictive", "proactive", {})
    assert not include_optional_evidence("relational", "proactive", {})
    assert include_optional_evidence("causal", "proactive", {"requires_causal": True})
