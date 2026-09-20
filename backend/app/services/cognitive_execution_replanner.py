"""Phase C — replanner with budgets for cross-source analyst paths (GA4 + optional GSC)."""
from __future__ import annotations

from uuid import uuid4

from app.capability_ontology.recipe_resolver import resolve_recipe
from app.services.connector_semantic_registry import (
    mentions_analytics_traffic_language,
    mentions_website_performance_language,
)
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep

DEFAULT_REPLAN_BUDGET = 1
TRAFFIC_RECIPE_ID = "analytics.website-traffic-overview"


def build_cross_source_analytics_plan(
    message: str,
    *,
    capability_id: str | None,
    connected_integrations: list[str] | None,
) -> ExecutionPlan | None:
    """GA4 + Search Console, or Search Console alone when Analytics is missing."""
    text = (message or "").strip()
    if not text:
        return None
    cap = str(capability_id or "").strip().lower()
    traffic_shaped = (
        cap in {"", "analytics.traffic_overview", "analytics.query", "search.performance"}
        or mentions_analytics_traffic_language(text)
        or mentions_website_performance_language(text)
    )
    if not traffic_shaped:
        return None

    connected = [str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()]
    has_ga = "google_analytics" in connected
    has_gsc = "google_search_console" in connected
    # GA-only stays on the HMAC traffic handler (richer PoP copy). This planner
    # runs when Search Console can contribute — alone or with GA.
    if not has_gsc:
        return None

    resolved = resolve_recipe(
        TRAFFIC_RECIPE_ID,
        connected_integrations=connected,
        query=text,
    )
    if resolved is None:
        return None
    by_id = {step.step_id: step for step in resolved.steps}
    ga4 = by_id.get("read_ga4")
    gsc = by_id.get("read_gsc")
    steps: list[ExecutionStep] = []
    if has_ga and ga4 and ga4.resolved_action:
        steps.append(
            ExecutionStep(
                step_id="read_ga4_traffic",
                title=ga4.name,
                kind="read",
                connector_id=ga4.resolved_vendor,
                capability_id=ga4.capability_id,
                action_key=ga4.resolved_action,
            )
        )
    if has_gsc and gsc and gsc.resolved_action:
        steps.append(
            ExecutionStep(
                step_id="read_gsc_performance",
                title=gsc.name,
                kind="read",
                connector_id=gsc.resolved_vendor,
                capability_id=gsc.capability_id,
                action_key=gsc.resolved_action,
                meta={"dimensions": ["page"], "safe_aggregate": True},
            )
        )
    if not steps:
        return None
    steps.append(
        ExecutionStep(
            step_id="compose_cross_source",
            title="Compose website performance summary",
            kind="compose",
            capability_id=cap or "analytics.traffic_overview",
            status="pending",
        )
    )
    summary = (
        "Website traffic overview (Analytics + Search)"
        if has_ga
        else "Website search performance (Analytics not connected)"
    )
    return ExecutionPlan(
        plan_id=str(uuid4()),
        summary=summary,
        steps=steps,
        source="cross_source_analytics_replanner",
        capability_id=cap or "analytics.traffic_overview",
        replan_budget=DEFAULT_REPLAN_BUDGET,
    )


def replan_budget_remaining(plan: ExecutionPlan) -> int:
    return max(0, int(plan.replan_budget) - int(plan.replans_used))


def should_replan(plan: ExecutionPlan, *, partial_failure: bool) -> bool:
    if not partial_failure:
        return False
    if replan_budget_remaining(plan) <= 0:
        return False
    return any(s.kind == "read" and s.status == "failed" for s in plan.steps)
