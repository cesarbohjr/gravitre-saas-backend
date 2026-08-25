"""Match department recipes to user intent for CognitivePlanner PLAN stage."""
from __future__ import annotations

from typing import Any

from app.capability_ontology.recipe_resolver import ResolvedRecipe, resolve_recipe
from app.capability_ontology.recipes import DepartmentRecipe, get_recipe, list_recipes

_RECIPE_TRIGGERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "sales.new-lead-enrichment",
        (
            "lead enrichment",
            "enrich this lead",
            "enrich lead",
            "new lead enrichment",
            "enrich the lead",
        ),
    ),
    (
        "hr.employee-onboarding",
        (
            "employee onboarding",
            "onboard new hire",
            "new hire onboarding",
            "onboarding kickoff",
            "welcome new employee",
        ),
    ),
    (
        "sales.inbound-triage",
        (
            "inbound triage",
            "triage inbound",
            "inbound lead",
            "triage this lead",
        ),
    ),
)


def match_recipe_for_query(
    query: str,
    *,
    department: str | None = None,
) -> DepartmentRecipe | None:
    """Return the best-matching department recipe for a user message."""
    text = str(query or "").strip().lower()
    if not text:
        return None
    dept_hint = str(department or "").strip().lower()
    best: DepartmentRecipe | None = None
    best_score = 0
    for recipe_id, phrases in _RECIPE_TRIGGERS:
        recipe = get_recipe(recipe_id)
        if not recipe:
            continue
        for phrase in phrases:
            if phrase not in text:
                continue
            score = len(phrase)
            if dept_hint and recipe.department == dept_hint:
                score += 10
            if score > best_score:
                best = recipe
                best_score = score
    return best


def recipe_plan_steps(resolved: ResolvedRecipe) -> list[dict[str, Any]]:
    """Convert a resolved recipe into cognitive plan step dicts."""
    steps: list[dict[str, Any]] = []
    for step in resolved.steps:
        if step.step_type == "trigger":
            continue
        description = step.name
        if step.resolved_vendor and step.resolved_action:
            vendor = step.resolved_vendor.replace("_", " ").title()
            description = f"{step.name} ({vendor}: {step.resolved_action})"
        elif step.capability_id:
            description = f"{step.name} ({step.capability_id})"
        steps.append(
            {
                "step_id": f"recipe_{step.step_id}",
                "title": step.name,
                "description": description,
                "status": "pending",
                "recipe_step_id": step.step_id,
                "capability_id": step.capability_id,
                "resolved_action": step.resolved_action,
                "resolved_vendor": step.resolved_vendor,
                "ambiguous": step.ambiguous,
            }
        )
    return steps


def enrich_plan_with_recipe(
    plan: dict[str, Any],
    *,
    query: str,
    connected_integrations: list[str] | None,
    department: str | None = None,
) -> dict[str, Any]:
    """Augment a cognitive plan with resolved capability-recipe workflow steps."""
    recipe = match_recipe_for_query(query, department=department)
    if not recipe:
        return plan
    resolved = resolve_recipe(
        recipe.recipe_id,
        connected_integrations=connected_integrations,
        query=query,
    )
    if resolved is None:
        return plan
    recipe_steps = recipe_plan_steps(resolved)
    if not recipe_steps:
        return plan

    out = dict(plan)
    existing = list(out.get("steps") or [])
    insert_at = 0
    for index, step in enumerate(existing):
        if str(step.get("step_id") or "") in {"understand", "apply_context"}:
            insert_at = index + 1
    out["steps"] = existing[:insert_at] + recipe_steps + existing[insert_at:]
    out["recipe"] = resolved.to_dict()
    out["summary"] = f"{recipe.name}: {out.get('summary') or query[:240]}"
    out["source"] = "cognitive_planner+recipe"
    return out
