"""Tests for Phase 3.1 Meson / dependency recipe hints."""
from __future__ import annotations

from app.capability_ontology.meson_recipe_hints import (
    format_recipe_prompt_section,
    recipe_hints_for_department,
    recipes_affected_by_connector_removal,
)


def test_recipe_hints_for_sales_department():
    hints = recipe_hints_for_department(
        department="sales",
        connected_integrations=["hubspot", "slack", "google_drive"],
        query="new lead",
    )
    assert hints
    assert any(h["recipeId"] == "sales.new-lead-enrichment" for h in hints)


def test_format_recipe_prompt_section_includes_capability_ids():
    section = format_recipe_prompt_section(
        department="sales",
        connected_integrations=["hubspot", "slack"],
        query="enrich lead",
    )
    assert "sales.new-lead-enrichment" in section
    assert "crm.contact" in section or "hubspot" in section


def test_recipes_affected_by_connector_removal():
    affected = recipes_affected_by_connector_removal("hubspot")
    assert any(row["recipeId"] == "sales.new-lead-enrichment" for row in affected)
