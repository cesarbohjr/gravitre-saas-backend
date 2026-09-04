"""Complexity routing guardrails — high-risk requests never downgrade for cost."""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from app.config import MODEL_TIERS
from app.services.assistant_routing_tier import (
    LATENCY_BUDGETS,
    ROUTING_TIERS,
    RoutingDecision,
    _TIER_RANK,
    _normalize_tier,
    model_tier_key_for_routing_tier,
    task_type_for_routing_tier,
)
from app.services.model_router import TaskType, _MODEL_PRICING_PER_1K

RISK_STANDARD = "standard"
RISK_HIGH = "high_risk"

_HIGH_RISK_LEGAL = re.compile(
    r"\b("
    r"legal|contract|liability|compliance|regulatory|gdpr|hipaa|sox|"
    r"lawsuit|indemnif|litigation|subpoena|warrant|termination\s+for\s+cause"
    r")\b",
    re.I,
)
_HIGH_RISK_FINANCIAL = re.compile(
    r"\b("
    r"audit|sec\s+filing|material\s+misstatement|financial\s+report|"
    r"tax\s+liability|wire\s+transfer|insider\s+trading|payroll\s+fraud|"
    r"bankruptcy|covenant\s+breach"
    r")\b",
    re.I,
)
_SIMPLE_EXTRACTION = re.compile(
    r"^\s*(what\s+is|who\s+is|define|list|show\s+me|how\s+many)\b",
    re.I,
)

# Representative synthesis COGS basis (1 turn, ~2k in / ~500 out tokens).
_COGS_INPUT_TOKENS = 2000
_COGS_OUTPUT_TOKENS = 500


def assess_message_risk_class(
    message: str,
    classification: dict[str, Any] | None = None,
) -> str:
    """Classify turn risk for routing floor (legal/financial/consequential)."""
    cls = classification if isinstance(classification, dict) else {}
    risk = str(cls.get("risk_level") or "").lower()
    if risk in {"high", "critical"}:
        return RISK_HIGH
    if bool(cls.get("requires_approval")) or bool(cls.get("requires_write_approval")):
        return RISK_HIGH
    if bool(cls.get("is_write")) or bool(cls.get("is_destructive")):
        return RISK_HIGH
    intent = str(cls.get("intent") or "").lower()
    if intent in {"write_confirm", "enrich", "extension_action", "workflow_execution"}:
        return RISK_HIGH

    text = str(message or "")
    if _HIGH_RISK_LEGAL.search(text) or _HIGH_RISK_FINANCIAL.search(text):
        return RISK_HIGH
    return RISK_STANDARD


def minimum_routing_tier_for_risk(risk_class: str) -> str:
    """High-risk turns must use research (frontier synthesis + mandatory critic path)."""
    if risk_class == RISK_HIGH:
        return "research"
    return "simple"


def guard_routing_tier_downgrade(
    proposed_tier: str,
    *,
    risk_class: str,
    misclassified_as_simple: bool = False,
) -> str:
    """Pure guard used in production and mutation tests.

    When ``misclassified_as_simple`` is True (mutation test), a high-risk turn
    that was wrongly labeled simple must still floor to research.
    """
    tier = _normalize_tier(proposed_tier)
    floor = minimum_routing_tier_for_risk(risk_class)
    if risk_class == RISK_HIGH and _TIER_RANK.get(tier, 0) < _TIER_RANK[floor]:
        return floor
    if misclassified_as_simple and risk_class == RISK_HIGH and tier == "simple":
        return "research"
    return tier


def requires_mandatory_critic(
    message: str,
    classification: dict[str, Any] | None = None,
) -> bool:
    """Extend consequential-write critic to legal/financial high-risk reads."""
    cls = classification if isinstance(classification, dict) else {}
    if assess_message_risk_class(message, cls) == RISK_HIGH:
        return True
    if bool(cls.get("requires_approval")) or bool(cls.get("requires_write_approval")):
        return True
    if bool(cls.get("is_write")) or bool(cls.get("is_destructive")):
        return True
    if str(cls.get("risk_level") or "").lower() in {"high", "critical"}:
        return True
    intent = str(cls.get("intent") or "").lower()
    return intent in {"write_confirm", "enrich", "extension_action", "workflow_execution"}


def apply_routing_risk_floor(
    decision: RoutingDecision,
    message: str,
    classification: dict[str, Any] | None = None,
) -> RoutingDecision:
    """Escalate-only: never downgrade high-risk below research tier."""
    risk = assess_message_risk_class(message, classification)
    floor_tier = guard_routing_tier_downgrade(decision.tier, risk_class=risk)
    if floor_tier == decision.tier:
        return decision
    budget = dict(LATENCY_BUDGETS[floor_tier])
    model_tier = model_tier_key_for_routing_tier(floor_tier)
    reasons = list(decision.reasons)
    reasons.append("high_risk_routing_floor")
    return replace(
        decision,
        tier=floor_tier,
        model_tier=model_tier,
        model=MODEL_TIERS.get(model_tier, MODEL_TIERS["medium"])["openai"],
        max_tool_rounds=budget["max_tool_rounds"],
        latency_budget=budget,
        pinned_fast=False if risk == RISK_HIGH else decision.pinned_fast,
        task_type=task_type_for_routing_tier(floor_tier),
        reasons=reasons,
    )


def classify_complexity_bucket(message: str) -> str:
    """Product complexity bucket for COGS reporting (not routing tier alone)."""
    text = str(message or "").strip()
    if assess_message_risk_class(text) == RISK_HIGH:
        return "legal_high_risk"
    if _SIMPLE_EXTRACTION.search(text) and len(text.split()) < 25:
        return "simple_extraction"
    if re.search(r"\b(analy[sz]e|compare|investigate|research|strategy)\b", text, re.I):
        return "strategic_reasoning"
    if re.search(r"\b(document|policy|according to|knowledge base|our docs)\b", text, re.I):
        return "rag_grounded"
    return "rag_grounded"


def _estimate_model_cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    pricing = _MODEL_PRICING_PER_1K.get(model_id)
    if not pricing:
        return 0.0
    in_rate, _, out_rate = pricing
    return round((input_tokens / 1000.0) * in_rate + (output_tokens / 1000.0) * out_rate, 6)


def estimate_routing_tier_cogs_usd(tier: str) -> float:
    """Estimated synthesis COGS for one assistant turn at a routing tier."""
    tier_key = _normalize_tier(tier)
    if tier_key not in ROUTING_TIERS:
        tier_key = "multi_step"
    model_tier = model_tier_key_for_routing_tier(tier_key)
    model_id = MODEL_TIERS.get(model_tier, MODEL_TIERS["medium"])["openai"]
    return _estimate_model_cost_usd(model_id, _COGS_INPUT_TOKENS, _COGS_OUTPUT_TOKENS)


def estimate_cogs_delta_simple_vs_prior(message: str) -> dict[str, Any]:
    """Honest before/after COGS using representative token assumptions."""
    # Prior default: everything non-voice landed multi_step unless explicit research.
    before_tier = "multi_step"
    after_decision_tier = "simple" if classify_complexity_bucket(message) == "simple_extraction" else "multi_step"
    if assess_message_risk_class(message) == RISK_HIGH:
        after_decision_tier = "research"
    before = estimate_routing_tier_cogs_usd(before_tier)
    after = estimate_routing_tier_cogs_usd(after_decision_tier)
    return {
        "assumptions": {
            "input_tokens": _COGS_INPUT_TOKENS,
            "output_tokens": _COGS_OUTPUT_TOKENS,
            "basis": "synthesis phase only; excludes tools/embeddings/critic",
        },
        "before_tier": before_tier,
        "after_tier": after_decision_tier,
        "before_usd": before,
        "after_usd": after,
        "delta_usd": round(after - before, 6),
        "task_type_before": TaskType.WORKFLOW_PLANNING.value,
        "task_type_after": task_type_for_routing_tier(after_decision_tier).value,
    }
