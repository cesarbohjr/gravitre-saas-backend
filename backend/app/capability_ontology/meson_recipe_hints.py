"""Capability recipe hints for Meson / GoalService workflow planning (Phase 3.1)."""
from __future__ import annotations

from typing import Any

from app.capability_ontology.recipe_resolver import resolve_recipe
from app.capability_ontology.recipes import DepartmentRecipe, list_recipes


def recipe_hints_for_department(
    *,
    department: str | None,
    connected_integrations: list[str] | None,
    query: str = "",
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return resolved recipe summaries suitable for LLM workflow prompts."""
    dept = str(department or "").strip().lower()
    if not dept:
        return []
    connected = [str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()]
    hints: list[dict[str, Any]] = []
    for recipe in list_recipes(department=dept):
        resolved = resolve_recipe(
            recipe.recipe_id,
            connected_integrations=connected,
            query=query,
        )
        hints.append(
            {
                "recipeId": recipe.recipe_id,
                "name": recipe.name,
                "status": resolved.status,
                "steps": [
                    {
                        "name": step.name,
                        "capabilityId": step.capability_id,
                        "resolvedAction": step.resolved_action,
                        "resolvedVendor": step.resolved_vendor,
                    }
                    for step in resolved.steps
                ],
            }
        )
        if len(hints) >= limit:
            break
    return hints


def format_recipe_prompt_section(
    *,
    department: str | None,
    connected_integrations: list[str] | None,
    query: str = "",
) -> str:
    hints = recipe_hints_for_department(
        department=department,
        connected_integrations=connected_integrations,
        query=query,
    )
    if not hints:
        return ""
    lines = [
        "Capability department recipes (prefer capability ids over hard-coded vendor actions):"
    ]
    for hint in hints:
        step_bits = []
        for step in hint.get("steps") or []:
            if not isinstance(step, dict):
                continue
            cap = step.get("capabilityId") or step.get("name")
            vendor = step.get("resolvedVendor")
            action = step.get("resolvedAction")
            if vendor and action:
                step_bits.append(f"{cap}→{vendor}:{action}")
            elif cap:
                step_bits.append(str(cap))
        lines.append(
            f"- {hint.get('recipeId')} ({hint.get('name')}): "
            f"status={hint.get('status')}; steps: {', '.join(step_bits) or 'n/a'}"
        )
    return "\n".join(lines)


def recipes_affected_by_connector_removal(
    connector_id: str,
    *,
    connected_integrations: list[str] | None = None,
) -> list[dict[str, Any]]:
    """DependencyImpact helper — recipes whose resolved steps use this connector."""
    vendor = str(connector_id or "").strip().lower()
    if not vendor:
        return []
    connected = {str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()}
    if connected and vendor not in connected:
        connected = {*connected, vendor}
    elif not connected:
        connected = {vendor}
    affected: list[dict[str, Any]] = []
    for recipe in list_recipes():
        resolved = resolve_recipe(recipe.recipe_id, connected_integrations=sorted(connected))
        hit_steps = [
            step.step_id
            for step in resolved.steps
            if step.resolved_vendor == vendor
        ]
        if hit_steps:
            affected.append(
                {
                    "recipeId": recipe.recipe_id,
                    "name": recipe.name,
                    "department": recipe.department,
                    "stepIds": hit_steps,
                }
            )
    return affected
