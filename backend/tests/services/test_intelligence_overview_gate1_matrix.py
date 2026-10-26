"""All seven tenant-wide capability settings must have three distinct evidence policies."""
from app.services.intelligence_overview_policy import (
    CAPABILITIES, evidence_threshold, apply_response_sensitivity,
    select_enrichment_work,
)


def test_every_capability_conservative_balanced_proactive_have_monotonic_thresholds():
    assert len(CAPABILITIES) == 7
    for capability in CAPABILITIES:
        a, b, c = (evidence_threshold(capability, mode) for mode in
                   ("conservative", "balanced", "proactive"))
        assert 0 < c < b < a <= 1


def test_all_seven_modes_make_distinct_evidence_decisions():
    slots = {key: {"status": "available", "confidence": 0.70, "data": {"source": "unit-test"}}
             for key in CAPABILITIES}
    base = {"enrichments": {"capabilities": slots}, "actions_taken": [],
            "actions_pending_approval": []}
    conservative = apply_response_sensitivity(base, {k: "conservative" for k in CAPABILITIES})
    proactive = apply_response_sensitivity(base, {k: "proactive" for k in CAPABILITIES})
    for key in CAPABILITIES:
        assert "data" not in conservative["enrichments"]["capabilities"][key]
        assert proactive["enrichments"]["capabilities"][key]["data"]["source"] == "unit-test"
    assert proactive["actions_taken"] == []
    assert proactive["actions_pending_approval"] == []


def test_proactive_optional_routing_still_never_overrides_deferred_or_unrelated_requests():
    policy = {"predictive": "proactive", "relational": "proactive", "adaptive": "proactive"}
    unrelated = select_enrichment_work({}, {}, policy)
    assert all(value is False for value in unrelated.values())
    deferred = select_enrichment_work(
        {"requires_prediction": True, "requires_graph": True, "requires_causal": True},
        {"defer_optional": True, "understanding": {"text": "hello"}}, policy)
    assert all(value is False for value in deferred.values())
