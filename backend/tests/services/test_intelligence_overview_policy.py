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


def test_each_capability_has_distinct_surfacing_thresholds():
    from app.services.intelligence_overview_policy import CAPABILITIES, evidence_threshold
    for capability in CAPABILITIES:
        assert evidence_threshold(capability, "conservative") > evidence_threshold(capability, "balanced") > evidence_threshold(capability, "proactive")


def test_low_confidence_evidence_is_suppressed_without_changing_actions():
    from app.services.intelligence_overview_policy import CAPABILITIES, apply_response_sensitivity
    data = {"enrichments": {"capabilities": {name: {"status": "available", "confidence": .6, "data": {"v": 1}} for name in CAPABILITIES}},
            "actions_taken": []}
    output = apply_response_sensitivity(data, {name: "conservative" for name in CAPABILITIES})
    assert all("data" not in output["enrichments"]["capabilities"][name] for name in CAPABILITIES)
    assert output["actions_taken"] == []


def test_optional_inference_routing_respects_explicit_vs_proactive():
    from app.services.intelligence_overview_policy import select_enrichment_work
    proposed = {"department": "sales", "metric": "revenue"}
    conservative = select_enrichment_work(proposed, {}, {"predictive": "conservative"})
    proactive = select_enrichment_work(proposed, {}, {"predictive": "proactive"})
    assert conservative["predictive"] is False
    assert proactive["predictive"] is True
    assert select_enrichment_work({"requires_prediction": True}, {}, {"predictive": "conservative"})["predictive"]
    assert not select_enrichment_work(proposed, {"defer_optional": True}, {"predictive": "proactive"})["predictive"]


def test_baseline_adaptive_evidence_remains_enabled_for_optional_requested_work():
    from app.services.intelligence_overview_policy import select_enrichment_work
    eligibility = select_enrichment_work(
        {"requires_prediction": True, "requires_causal": True},
        {"understanding": {"goal": "review"}},
        {},
    )
    assert eligibility["adaptive"] is True
    assert eligibility["predictive"] is True
    assert eligibility["causal"] is True
    deferred = select_enrichment_work(
        {"requires_prediction": True}, {"defer_optional": True}, {},
    )
    assert not any(deferred.values())


def test_turned_off_ability_does_no_work_and_shows_no_evidence():
    from app.services.intelligence_overview_policy import apply_response_sensitivity, select_enrichment_work
    policy = normalize_policy({"causal": {"mode": "proactive", "enabled": False}, "temporal": {"enabled": False}})
    assert policy["causal"] == "off"
    assert policy["temporal"] == "balanced"
    work = select_enrichment_work({"requires_causal": True, "requires_prediction": True}, {}, policy)
    assert work["causal"] is False
    assert work["predictive"] is True
    out = apply_response_sensitivity(
        {"enrichments": {"capabilities": {"causal": {"status": "ok", "confidence": 0.99, "data": {"x": 1}}}}}, policy
    )
    slot = out["enrichments"]["capabilities"]["causal"]
    assert "data" not in slot
    assert slot["suppression_reason"] == "turned_off"
