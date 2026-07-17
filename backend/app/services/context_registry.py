"""Context registry — decide which context slices to load per turn (Tier 1).

Manus-style context engineering: load only relevant connector, department, company,
user, workflow, RAG, and graph slices instead of assembling everything every turn.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.core.logging import get_logger

logger = get_logger(__name__)

ContextSlice = Literal[
    "connector",
    "department",
    "company",
    "user",
    "workflow",
    "rag",
    "graph",
    "signals",
]

_ALL_SLICES: frozenset[str] = frozenset(
    {"connector", "department", "company", "user", "workflow", "rag", "graph", "signals"}
)

_CONNECTOR_HINT = re.compile(
    r"\b(apollo|hubspot|slack|salesforce|jira|github|notion|stripe|asana|gmail|"
    r"monday|pipedrive|zendesk|connector|integration|crm|erp)\b",
    re.I,
)
_ACTION_HINT = re.compile(
    r"\b(create|update|delete|send|post|assign|execute|run|workflow|orchestrat|notify)\b",
    re.I,
)


@dataclass(frozen=True)
class ContextRegistryPlan:
    """Resolved context plan for a single assistant turn."""

    enabled_slices: frozenset[str]
    token_budget: int
    rag_top_k: int
    connector_names: tuple[str, ...] = ()
    routing_tier: str = "multi_step"
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def slice_enabled(self, slice_name: str) -> bool:
        return slice_name in self.enabled_slices

    def to_explanation_dict(self) -> dict[str, Any]:
        return {
            "enabledSlices": sorted(self.enabled_slices),
            "tokenBudget": self.token_budget,
            "ragTopK": self.rag_top_k,
            "connectorNames": list(self.connector_names),
            "routingTier": self.routing_tier,
            "reasons": list(self.reasons),
        }


def _mentioned_connectors(text: str, connected: list[str]) -> list[str]:
    lower = text.lower()
    hits = [name for name in connected if name.lower() in lower]
    if hits:
        return hits
    if _CONNECTOR_HINT.search(text):
        return list(connected)
    return []


def plan_context_registry(
    *,
    query: str,
    classification: dict[str, Any],
    connected_integrations: list[str] | None = None,
    task_state: dict[str, Any] | None = None,
    routing_tier: str | None = None,
    mode: str | None = None,
) -> ContextRegistryPlan:
    """Build a slice plan from classification, routing tier, and task signals."""
    text = (query or "").strip()
    connected = [str(c).strip() for c in (connected_integrations or []) if str(c).strip()]
    tier = str(routing_tier or "multi_step").replace("-", "_")
    mode_key = str(mode or "standard").strip().lower()
    intent = str(classification.get("intent") or "").lower()
    requires_action = bool(classification.get("requires_action"))
    requires_graph = bool(classification.get("requires_graph"))
    department = str(classification.get("department") or "").strip()
    pending = (task_state or {}).get("pending_task") or {}
    has_workflow_state = bool(
        pending
        or (task_state or {}).get("current_plan")
        or (task_state or {}).get("pending_steps")
        or (task_state or {}).get("clarified_params")
    )

    reasons: list[str] = []
    enabled: set[str] = {"user", "rag"}

    if tier == "simple" and mode_key == "fast" and not requires_action:
        token_budget = 8_000
        rag_top_k = 4
        reasons.append("fast_simple_budget")
    elif tier == "research":
        token_budget = 16_000
        rag_top_k = 10
        enabled.update({"company", "graph", "signals", "department", "workflow"})
        reasons.append("research_full_context")
    else:
        token_budget = 12_000
        rag_top_k = 6
        reasons.append("standard_budget")

    connector_hits = _mentioned_connectors(text, connected)
    if connector_hits or requires_action or _CONNECTOR_HINT.search(text):
        enabled.add("connector")
        reasons.append("connector_relevant")
    if department:
        enabled.add("department")
        reasons.append("department_set")
    if requires_graph or intent in {"analytics", "risk_analysis", "relationship_lookup"}:
        enabled.add("graph")
        reasons.append("graph_intent")
    if intent in {"workflow_execution", "agent_management", "connector_management"} or has_workflow_state:
        enabled.add("workflow")
        enabled.add("connector")
        reasons.append("workflow_state")
    if requires_action and tier != "simple":
        enabled.add("company")
        enabled.add("signals")
        reasons.append("action_signals")
    if _ACTION_HINT.search(text) and connected:
        enabled.add("connector")
        reasons.append("action_with_connectors")

    # Never load graph/company on pure fast lookups.
    if tier == "simple" and not requires_graph and intent == "knowledge_lookup":
        enabled.discard("graph")
        enabled.discard("company")
        enabled.discard("signals")
        reasons.append("simple_lookup_trim")

    enabled &= set(_ALL_SLICES)

    return ContextRegistryPlan(
        enabled_slices=frozenset(enabled),
        token_budget=token_budget,
        rag_top_k=rag_top_k,
        connector_names=tuple(connector_hits or connected[:3]),
        routing_tier=tier,
        reasons=tuple(reasons),
    )


def filter_context_sources(
    raw_sources: list[Any],
    plan: ContextRegistryPlan,
) -> list[Any]:
    """Drop raw context sources outside the registry plan."""
    slice_map = {
        "org_context": "company",
        "rag": "rag",
        "agent_memory": "user",
        "conversation_memory": "user",
        "company_intelligence": "company",
        "graph": "graph",
        "entity_graph": "graph",
        "connector_context": "connector",
        "task_state": "workflow",
    }
    kept: list[Any] = []
    for source in raw_sources:
        source_type = getattr(source, "source_type", None) or (source.get("source_type") if isinstance(source, dict) else "")
        slice_name = slice_map.get(str(source_type), "rag")
        if slice_name in plan.enabled_slices:
            kept.append(source)
    return kept


_registry_plan_cache: dict[str, ContextRegistryPlan] | None = None


def get_context_registry_plan(**kwargs: Any) -> ContextRegistryPlan:
    return plan_context_registry(**kwargs)
