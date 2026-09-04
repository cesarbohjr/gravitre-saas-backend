"""Routing wave — product tiers simple / multi_step / research.

Classifies assistant turns into named latency budgets and supports escalate-only
mid-turn upgrades. Does not change write-approval / execute_plan contracts —
routing selects model class and iteration caps only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from app.config import MODEL_TIERS
from app.services.model_router import TaskType

ROUTING_TIERS = ("simple", "multi_step", "research")
ROUTING_PHASES = ("classification", "planning", "synthesis", "verification")

# Tier 1 model cascade — cheapest capable model per phase.
_PHASE_MODEL_TIER: dict[str, dict[str, str]] = {
    "simple": {
        "classification": "low",
        "planning": "low",
        "synthesis": "medium",
        "verification": "low",
    },
    "multi_step": {
        "classification": "low",
        "planning": "medium",
        "synthesis": "medium",
        "verification": "low",
    },
    "research": {
        "classification": "low",
        "planning": "medium",
        "synthesis": "high",
        "verification": "low",
    },
}

LATENCY_BUDGETS: dict[str, dict[str, int]] = {
    "simple": {"ttft_ms": 800, "total_ms": 8000, "max_tool_rounds": 2},
    "multi_step": {"ttft_ms": 1500, "total_ms": 20000, "max_tool_rounds": 6},
    "research": {"ttft_ms": 2500, "total_ms": 60000, "max_tool_rounds": 12},
}

_TIER_RANK = {"simple": 0, "multi_step": 1, "research": 2}

_WRITE_INTENT = re.compile(
    r"\b(create|update|delete|send|post|assign|enroll|trigger|execute|run|write|"
    r"close|notify|message|sync|add|remove|publish)\b",
    re.I,
)
_CONNECTOR_HINT = re.compile(
    r"\b(apollo|hubspot|slack|salesforce|jira|github|notion|stripe|asana|gmail|"
    r"monday|pipedrive|zendesk|connector|integration)\b",
    re.I,
)
_MULTI_STEP_HINT = re.compile(
    r"\b(then|after that|next|and also|multi[- ]?step|plan|workflow|orchestrat|"
    r"step by step)\b",
    re.I,
)
_RESEARCH_HINT = re.compile(
    r"\b(analy[sz]e|compare|investigate|research|deep dive|full analysis|"
    r"across (all|every)|synthesize)\b",
    re.I,
)
_DEEPEN_HINT = re.compile(
    r"\b(go deeper|dig (in|deeper)|full analysis|more detail|be thorough|"
    r"research (this|it)|expand on)\b",
    re.I,
)


@dataclass
class RoutingDecision:
    tier: str
    model_tier: str
    model: str
    max_tool_rounds: int
    latency_budget: dict[str, int]
    reasons: list[str] = field(default_factory=list)
    pinned_fast: bool = False
    task_type: TaskType = TaskType.RAG_ANSWERING

    def to_sse(self) -> dict[str, Any]:
        return {
            "routingTier": self.tier,
            "modelTier": self.model_tier,
            "latencyBudgetMs": {
                "ttft": self.latency_budget["ttft_ms"],
                "total": self.latency_budget["total_ms"],
            },
            "maxToolRounds": self.max_tool_rounds,
            "pinnedFast": self.pinned_fast,
            "reasons": list(self.reasons),
        }


@dataclass
class RoutingControl:
    """Mutable mid-turn routing state (escalate-only)."""

    tier: str
    model: str
    max_iterations: int
    pinned_fast: bool = False
    consecutive_tool_failures: int = 0
    escalations: list[dict[str, Any]] = field(default_factory=list)
    model_resolver: Callable[[str], str] | None = None

    def escalate(self, to_tier: str, reason: str) -> bool:
        to_tier = _normalize_tier(to_tier)
        if _TIER_RANK[to_tier] <= _TIER_RANK.get(self.tier, 0):
            return False
        if self.pinned_fast and to_tier != "simple" and reason != "user_deepen":
            return False
        from_tier = self.tier
        from_model = self.model
        self.tier = to_tier
        budget = LATENCY_BUDGETS[to_tier]
        self.max_iterations = max(self.max_iterations, budget["max_tool_rounds"])
        if self.model_resolver:
            self.model = self.model_resolver(to_tier)
        else:
            self.model = default_model_for_tier(to_tier)
        self.escalations.append(
            {
                "from_tier": from_tier,
                "to_tier": to_tier,
                "from_model": from_model,
                "to_model": self.model,
                "reason": reason,
            }
        )
        self.consecutive_tool_failures = 0
        return True


def _normalize_tier(tier: str) -> str:
    t = str(tier or "").strip().lower().replace("-", "_")
    if t in {"multi-step", "multistep", "multi_step"}:
        return "multi_step"
    if t in ROUTING_TIERS:
        return t
    return "multi_step"


def default_model_for_tier(tier: str) -> str:
    return model_for_routing_phase("synthesis", tier)


def model_for_routing_phase(phase: str, routing_tier: str) -> str:
    """Return OpenAI model id for a pipeline phase (escalate-only cascade)."""
    tier = _normalize_tier(routing_tier)
    phase_key = str(phase or "synthesis").strip().lower()
    if phase_key not in ROUTING_PHASES:
        phase_key = "synthesis"
    model_tier = _PHASE_MODEL_TIER.get(tier, _PHASE_MODEL_TIER["multi_step"]).get(
        phase_key, "medium"
    )
    return MODEL_TIERS.get(model_tier, MODEL_TIERS["medium"])["openai"]


def resolve_tool_loop_model(
    *,
    explicit_model: str | None,
    routing_control: "RoutingControl | None",
    phase: str,
    routing_tier: str,
) -> str:
    """Pick the inference model for a tool-calling iteration.

    When the agent (or caller) configured a non-OpenAI model, that selection locks
    the full tool loop — routing-tier OpenAI defaults must not override it.
    """
    from app.services.providers.provider_tool_router import resolve_provider_for_model

    locked = str(explicit_model or "").strip()
    if locked and resolve_provider_for_model(locked) != "openai":
        return locked
    if routing_control is not None and phase == "synthesis":
        return str(routing_control.model or "").strip() or model_for_routing_phase(
            phase, routing_tier
        )
    return model_for_routing_phase(phase, routing_tier)


def task_type_for_phase(phase: str) -> TaskType:
    return {
        "classification": TaskType.CLASSIFICATION,
        "planning": TaskType.WORKFLOW_PLANNING,
        "synthesis": TaskType.RAG_ANSWERING,
        "verification": TaskType.SUMMARIZATION,
    }.get(str(phase or "").strip().lower(), TaskType.RAG_ANSWERING)


def task_type_for_routing_tier(tier: str) -> TaskType:
    return {
        "simple": TaskType.SUMMARIZATION,
        "multi_step": TaskType.WORKFLOW_PLANNING,
        "research": TaskType.DECISION_REASONING,
    }.get(_normalize_tier(tier), TaskType.RAG_ANSWERING)


def model_tier_key_for_routing_tier(tier: str) -> str:
    return {
        "simple": "low",
        "multi_step": "medium",
        "research": "high",
    }.get(_normalize_tier(tier), "medium")


def classify_routing_tier(
    message: str,
    *,
    mode: str | None = None,
    connected_integrations: list[str] | None = None,
    parameters: dict[str, Any] | None = None,
    prior_tier: str | None = None,
    classification: dict[str, Any] | None = None,
) -> RoutingDecision:
    """Classify turn into simple / multi_step / research with latency budget."""
    from app.services.complexity_routing_guardrails import apply_routing_risk_floor, assess_message_risk_class

    params = parameters or {}
    reasons: list[str] = []
    mode_key = str(mode or "standard").strip().lower()
    text = str(message or "").strip()
    words = len(text.split())
    connected = [str(c).strip() for c in (connected_integrations or []) if str(c).strip()]
    pinned_fast = mode_key == "fast"
    high_risk = assess_message_risk_class(text, classification) == "high_risk"

    explicit = str(params.get("routing_tier") or params.get("complexity") or "").strip().lower()
    if explicit in {"research", "high", "complex"} or params.get("require_high_model"):
        tier = "research"
        reasons.append("explicit_high")
    elif explicit in {"simple", "low", "fast"} or (pinned_fast and not _DEEPEN_HINT.search(text)):
        tier = "simple"
        reasons.append("fast_or_explicit_simple")
    elif explicit in {"multi_step", "multi-step", "medium"}:
        tier = "multi_step"
        reasons.append("explicit_multi_step")
    elif mode_key in {"reasoning", "agent", "deep"}:
        tier = "research"
        reasons.append("agent_or_reasoning_mode")
    elif _DEEPEN_HINT.search(text) or _RESEARCH_HINT.search(text) or words > 400 or len(text) > 2500:
        tier = "research"
        reasons.append("research_signal")
    elif _WRITE_INTENT.search(text) and (connected or _CONNECTOR_HINT.search(text)):
        tier = "multi_step"
        reasons.append("write_intent_with_connector")
    elif _MULTI_STEP_HINT.search(text) or (connected and _CONNECTOR_HINT.search(text)):
        tier = "multi_step"
        reasons.append("multi_step_or_connector")
    elif pinned_fast and words < 80 and not high_risk:
        tier = "simple"
        reasons.append("fast_short")
    elif high_risk:
        tier = "research"
        reasons.append("high_risk_message_floor")
    else:
        tier = "multi_step" if words > 40 else "simple"
        reasons.append("default_length")

    # Never start below prior escalated tier within a thread (escalate-only memory).
    if prior_tier and _TIER_RANK.get(_normalize_tier(prior_tier), 0) > _TIER_RANK[tier]:
        if not (pinned_fast and not _DEEPEN_HINT.search(text)):
            tier = _normalize_tier(prior_tier)
            reasons.append("prior_tier_floor")

    # Pinned Fast: stay simple unless deepen OR explicit high/research override OR high-risk.
    if (
        pinned_fast
        and tier != "simple"
        and not high_risk
        and not _DEEPEN_HINT.search(text)
        and explicit not in {"research", "high", "complex"}
        and not params.get("require_high_model")
    ):
        tier = "simple"
        reasons.append("pinned_fast_cap")

    budget = dict(LATENCY_BUDGETS[tier])
    model_tier = model_tier_key_for_routing_tier(tier)
    decision = RoutingDecision(
        tier=tier,
        model_tier=model_tier,
        model=MODEL_TIERS.get(model_tier, MODEL_TIERS["medium"])["openai"],
        max_tool_rounds=budget["max_tool_rounds"],
        latency_budget=budget,
        reasons=reasons,
        pinned_fast=pinned_fast,
        task_type=task_type_for_routing_tier(tier),
    )
    return apply_routing_risk_floor(decision, text, classification)


def is_user_deepen_message(message: str) -> bool:
    return bool(_DEEPEN_HINT.search(str(message or "")))


def record_tool_outcome(control: RoutingControl, *, success: bool, error_code: str | None = None) -> bool:
    """Update failure streak; escalate after 2 consecutive interpretive failures."""
    if success:
        control.consecutive_tool_failures = 0
        return False
    # Soft / expected gate codes do not count as interpretive failure.
    soft = {
        "write_approval_required",
        "tool_not_available",
        "connector_not_connected",
        "validation_error",
    }
    if str(error_code or "") in soft:
        return False
    control.consecutive_tool_failures += 1
    if control.consecutive_tool_failures < 2:
        return False
    nxt = "multi_step" if control.tier == "simple" else "research"
    return control.escalate(nxt, "consecutive_tool_failures")


def escalate_for_write_tool(control: RoutingControl, *, tool_is_write: bool) -> bool:
    if not tool_is_write or control.tier != "simple":
        return False
    return control.escalate("multi_step", "write_tool_from_simple")


def escalate_for_user_deepen(control: RoutingControl, message: str) -> bool:
    if not is_user_deepen_message(message):
        return False
    return control.escalate("research", "user_deepen")
