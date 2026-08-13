"""Phase 3 — capability-referenced department recipes."""
from __future__ import annotations

from app.capability_ontology.recipe_resolver import resolve_recipe
from app.capability_ontology.recipes import get_recipe, list_recipes


def test_recipe_registry_has_core_department_recipes():
    ids = {r.recipe_id for r in list_recipes()}
    assert "sales.new-lead-enrichment" in ids
    assert "hr.employee-onboarding" in ids
    assert get_recipe("sales.inbound-triage") is not None


def test_lead_enrichment_resolves_hubspot_slack():
    resolved = resolve_recipe(
        "sales.new-lead-enrichment",
        connected_integrations=["hubspot", "slack", "google_drive"],
        query="enrich this lead in HubSpot",
    )
    assert resolved is not None
    assert resolved.status == "fully_resolved"
    by_id = {s.step_id: s for s in resolved.steps}
    assert by_id["search_crm"].resolved_action == "hubspot.contacts.search"
    assert by_id["write_crm"].resolved_action == "hubspot.contacts.create"
    assert by_id["notify"].resolved_action == "slack.post_message"
    assert by_id["search_docs"].resolved_action == "google_drive.search_files"


def test_lead_enrichment_microsoft_hubspot_stack():
    resolved = resolve_recipe(
        "sales.new-lead-enrichment",
        connected_integrations=["hubspot", "microsoft_teams", "notion"],
        preferred_vendor="hubspot",
    )
    assert resolved is not None
    assert resolved.status == "fully_resolved"
    by_id = {s.step_id: s for s in resolved.steps}
    assert by_id["write_crm"].resolved_vendor == "hubspot"
    assert by_id["notify"].resolved_action == "microsoft_teams.messages.send"
    assert by_id["search_docs"].resolved_action == "notion.search_files"


def test_multi_crm_recipe_is_ambiguous_without_hint():
    resolved = resolve_recipe(
        "sales.inbound-triage",
        connected_integrations=["hubspot", "salesforce", "slack"],
        query="triage this inbound lead",
    )
    assert resolved is not None
    assert resolved.status == "ambiguous"
    assert "lookup" in resolved.ambiguous_steps


def test_onboarding_resolves_google_stack():
    resolved = resolve_recipe(
        "hr.employee-onboarding",
        connected_integrations=["gmail", "google_calendar", "google_drive", "slack"],
    )
    assert resolved is not None
    assert resolved.status == "fully_resolved"
    by_id = {s.step_id: s for s in resolved.steps}
    assert by_id["welcome_email"].resolved_action == "gmail.messages.send"
    assert by_id["kickoff"].resolved_action == "google_calendar.events.create"
