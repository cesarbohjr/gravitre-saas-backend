"""Predictive context loading — adjust registry plan before parallel gather.

Cursor-style: most of the work happens before the expensive generation call.
Fail-open: never shrink below the caller's plan floors for required slices.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.services.context_registry import ContextRegistryPlan


def adjust_registry_plan_for_prediction(
    plan: ContextRegistryPlan,
    *,
    classification: dict[str, Any],
    query: str = "",
) -> ContextRegistryPlan:
    """Expand slices / top_k when intent signals need richer context ahead of generation."""
    conf = float(classification.get("classification_confidence") or classification.get("confidence") or 0.55)
    intent = str(classification.get("intent") or "").lower()
    requires_action = bool(classification.get("requires_action"))
    requires_graph = bool(classification.get("requires_graph"))
    department = str(classification.get("department") or "").strip().lower()

    enabled = set(plan.enabled_slices)
    reasons = list(plan.reasons)
    rag_top_k = int(plan.rag_top_k)
    token_budget = int(plan.token_budget)

    # Low classification confidence → retrieve more + enable graph/signals.
    if conf < 0.45:
        rag_top_k = max(rag_top_k, 10)
        token_budget = max(token_budget, 14_000)
        enabled.update({"company", "signals"})
        reasons.append("predictive_low_confidence_expand")

    # Research / analytics intents preload graph + company.
    if intent in {"analytics", "research", "risk_analysis", "relationship_lookup"} or requires_graph:
        enabled.update({"graph", "company", "signals"})
        rag_top_k = max(rag_top_k, 8)
        reasons.append("predictive_research_preload")

    # Action intents preload connectors + workflow scratchpad slices.
    if requires_action or intent in {"workflow_execution", "connector_management"}:
        enabled.update({"connector", "workflow", "signals"})
        reasons.append("predictive_action_preload")

    # Department-aware preload (sales/support/ops).
    if department in {"sales", "revenue", "marketing"}:
        enabled.add("connector")
        reasons.append("predictive_department_sales")
    elif department in {"support", "customer_success", "cs"}:
        enabled.update({"connector", "signals"})
        reasons.append("predictive_department_support")
    elif department in {"ops", "operations", "security", "finance"}:
        enabled.update({"company", "signals", "workflow"})
        reasons.append("predictive_department_ops")

    # Long queries often need more RAG budget.
    if len((query or "").split()) >= 40:
        rag_top_k = max(rag_top_k, 8)
        token_budget = max(token_budget, 14_000)
        reasons.append("predictive_long_query")

    # Deduplicate reasons while preserving order.
    seen: set[str] = set()
    ordered_reasons: list[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            ordered_reasons.append(reason)

    return replace(
        plan,
        enabled_slices=frozenset(enabled),
        rag_top_k=rag_top_k,
        token_budget=token_budget,
        reasons=tuple(ordered_reasons),
    )
