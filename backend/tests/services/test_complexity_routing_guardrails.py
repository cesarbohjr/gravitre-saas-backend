"""Complexity routing guardrails — high-risk never downgrades."""
from __future__ import annotations

from app.services.assistant_routing_tier import classify_routing_tier
from app.services.complexity_routing_guardrails import (
    apply_routing_risk_floor,
    assess_message_risk_class,
    estimate_cogs_delta_simple_vs_prior,
    guard_routing_tier_downgrade,
    requires_mandatory_critic,
)


def test_simple_request_routes_cheaper():
    decision = classify_routing_tier("What is Gravitre?", mode="fast")
    assert decision.tier == "simple"
    assert decision.model_tier == "low"
    cogs = estimate_cogs_delta_simple_vs_prior("What is Gravitre?")
    assert cogs["after_tier"] == "simple"
    assert cogs["delta_usd"] <= 0


def test_high_risk_legal_routes_research():
    msg = "Review our vendor contract for GDPR compliance liability exposure."
    decision = classify_routing_tier(msg, mode="fast")
    assert decision.tier == "research"
    assert decision.model_tier == "high"
    assert "high_risk" in " ".join(decision.reasons)


def test_high_risk_mandatory_critic():
    msg = "Does this SEC filing create material misstatement risk?"
    assert requires_mandatory_critic(msg, {"intent": "question_answering"})
    assert assess_message_risk_class(msg) == "high_risk"


def test_mutation_misclassified_high_risk_caught():
    """Deliberate misclassification as simple must be floored to research."""
    tier = guard_routing_tier_downgrade(
        "simple",
        risk_class="high_risk",
        misclassified_as_simple=True,
    )
    assert tier == "research"


def test_post_classification_floor_escalates():
    base = classify_routing_tier("Summarize yesterday's standup", mode="standard")
    assert base.tier in {"simple", "multi_step"}
    floored = apply_routing_risk_floor(
        base,
        "Approve wire transfer for vendor payout",
        {"risk_level": "high", "requires_approval": True},
    )
    assert floored.tier == "research"
