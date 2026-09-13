"""Phase C — replanner with budgets for cross-source analyst paths (GA4 + GSC)."""
from __future__ import annotations

from uuid import uuid4

from app.services.connector_semantic_registry import (
    mentions_website_performance_language,
    resolve_analytics_capabilities_for_message,
)
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep

DEFAULT_REPLAN_BUDGET = 1


def build_cross_source_analytics_plan(
    message: str,
    *,
    capability_id: str | None,
    connected_integrations: list[str] | None,
) -> ExecutionPlan | None:
    """When GA4 + GSC are connected and the user asks broad website performance, plan parallel reads."""
    text = (message or "").strip()
    if not text:
        return None
    cap = str(capability_id or "").strip().lower()
    if cap not in {"", "analytics.traffic_overview", "analytics.query"}:
        if not mentions_website_performance_language(text):
            return None

    connected = {str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()}
    caps = set(
        resolve_analytics_capabilities_for_message(text, connected_integrations=list(connected))
    )
    has_ga4 = "google_analytics" in connected
    has_gsc = "google_search_console" in connected
    if not (has_ga4 and has_gsc):
        return None
    if not (mentions_website_performance_language(text) or caps.intersection({"google_analytics", "google_search_console"})):
        return None

    steps: list[ExecutionStep] = [
        ExecutionStep(
            step_id="read_ga4_traffic",
            title="GA4 traffic overview",
            kind="read",
            connector_id="google_analytics",
            capability_id="analytics.traffic_overview",
            action_key="google_analytics.reports.run",
        ),
        ExecutionStep(
            step_id="read_gsc_performance",
            title="Search Console page performance",
            kind="read",
            connector_id="google_search_console",
            capability_id="analytics.query",
            action_key="google_search_console.searchAnalytics.query",
            meta={"dimensions": ["page"], "safe_aggregate": True},
        ),
        ExecutionStep(
            step_id="compose_cross_source",
            title="Compose website performance summary",
            kind="compose",
            capability_id="analytics.traffic_overview",
            status="pending",
        ),
    ]
    return ExecutionPlan(
        plan_id=str(uuid4()),
        summary="Cross-source website performance (GA4 + Search Console)",
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
