"""Tests for CognitivePlanner + capability recipe enrichment."""
from __future__ import annotations

from app.capability_ontology.cognitive_recipe_planner import (
    enrich_plan_with_recipe,
    match_recipe_for_query,
)
from app.services.cognitive_planner import CognitivePlanner


def test_match_recipe_for_onboarding_query():
    recipe = match_recipe_for_query("kick off employee onboarding for the new hire")
    assert recipe is not None
    assert recipe.recipe_id == "hr.employee-onboarding"


def test_cognitive_planner_enriches_lead_enrichment_plan():
    planner = CognitivePlanner()
    plan = planner.plan(
        "Please run lead enrichment for this inbound contact",
        None,
        None,
        None,
        connected_integrations=["hubspot", "slack", "google_drive"],
        department="sales",
    )
    assert plan.get("source") == "cognitive_planner+recipe"
    assert plan.get("recipe", {}).get("recipeId") == "sales.new-lead-enrichment"
    step_ids = [step.get("step_id") for step in plan.get("steps") or []]
    assert "recipe_search_crm" in step_ids
    assert "recipe_write_crm" in step_ids


def test_enrich_plan_without_match_is_unchanged():
    base = {"steps": [{"step_id": "understand"}], "summary": "hello", "source": "cognitive_planner"}
    out = enrich_plan_with_recipe(
        base,
        query="what is our ARR trend?",
        connected_integrations=["hubspot"],
    )
    assert out == base
