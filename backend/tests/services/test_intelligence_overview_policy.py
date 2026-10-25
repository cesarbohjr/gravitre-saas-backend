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


def test_all_seven_controls_expose_effect_and_filter_unverified_evidence():
    from app.services.intelligence_overview_policy import apply_response_sensitivity, CAPABILITIES
    evidence = {k: {"status": "insufficient_data", "data": {"unverified": True}} for k in CAPABILITIES}
    output = apply_response_sensitivity(
        {"enrichments": {"capabilities": evidence}},
        {k: "conservative" for k in CAPABILITIES},
    )
    for name in CAPABILITIES:
        slot = output["enrichments"]["capabilities"][name]
        assert slot["evidence_suppressed"]
        assert "data" not in slot
        assert slot["sensitivity_mode"] == "conservative"


def test_balanced_retains_provenance_and_never_invents_actions():
    from app.services.intelligence_overview_policy import apply_response_sensitivity
    initial = {"enrichments": {"capabilities": {"causal": {
        "status": "correlational_fallback",
        "data": {"note": "not causal proof"},
    }}}, "actions_taken": []}
    out = apply_response_sensitivity(initial, {"causal": "balanced"})
    assert out["enrichments"]["capabilities"]["causal"]["data"]["note"] == "not causal proof"
    assert out["actions_taken"] == []
