"""2.0-C operational source order: live systems before knowledge/web/model."""
from __future__ import annotations

from typing import Any, Literal

SourceTier = Literal[
    "live_systems",
    "org_graph",
    "company_knowledge",
    "memory",
    "expert",
    "web",
    "model",
]

SOURCE_ORDER: tuple[SourceTier, ...] = (
    "live_systems",
    "org_graph",
    "company_knowledge",
    "memory",
    "expert",
    "web",
    "model",
)

_OPERATIONAL_READ_RECIPES = frozenset(
    {
        "analytics.website-traffic-overview",
        "sales.pipeline.health",
        "finance.receivables.overdue",
        "support.issue_trends",
    }
)


def prefer_live_systems(message: str, *, connected_integrations: list[str] | None) -> bool:
    """True when a connected live system can answer an operational READ recipe."""
    from app.capability_ontology.cognitive_recipe_planner import match_recipe_for_query
    from app.capability_ontology.recipe_resolver import resolve_recipe
    from app.services.analytics_traffic_overview_service import should_suppress_knowledge_base_for_turn

    connected = [str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()]
    if should_suppress_knowledge_base_for_turn(
        message,
        connected_integrations=connected,
        task_state=None,
    ):
        return True
    recipe = match_recipe_for_query(message)
    if recipe is None or recipe.recipe_id not in _OPERATIONAL_READ_RECIPES:
        return False
    resolved = resolve_recipe(recipe.recipe_id, connected_integrations=connected, query=message)
    if resolved is None:
        return False
    return resolved.status in {"fully_resolved", "partial"} and any(
        s.resolved_action for s in resolved.steps if s.step_type == "invoke_tool" and not s.optional
    )
