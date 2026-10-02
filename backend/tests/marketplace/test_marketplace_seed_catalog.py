"""MKT-4: Starter marketplace catalog validation."""
from __future__ import annotations

import pytest

from app.marketplace.schemas import validate_asset_payload
from app.marketplace.seed_catalog import LEGACY_PACK_SLUG_MAP, catalog_assets_by_slug, list_catalog_assets


def test_catalog_asset_counts():
    assets = list_catalog_assets()
    by_type: dict[str, int] = {}
    for asset in assets:
        by_type[asset.asset_type] = by_type.get(asset.asset_type, 0) + 1
    assert by_type["ai_agent"] == 23
    assert by_type["workflow"] == 20
    assert by_type["knowledge_pack"] == 15
    assert by_type["department_pack"] == 6
    assert by_type["play"] == 8
    assert by_type["dataset_pack"] == 1
    assert by_type["dashboard_pack"] == 1
    assert by_type["outcome_pack"] == 1
    # 8 original packs + AI Search + Finance + HR Talent + Platform Health
    assert by_type.get("intelligence_pack", 0) == 12
    assert len(assets) == 87


# Formerly deferred Slice A binding failures — remediated (Part 2 finish).
_REMEDIATED_BINDING_SLUGS = frozenset(
    {
        "hubspot-lead-qualification",
        "customer-health-monitoring",
        "zendesk-ticket-triage",
        "lead-routing-automation",
        "qbr-preparation-workflow",
        "support-operations-pack",
    }
)


@pytest.mark.parametrize("asset_slug", sorted(catalog_assets_by_slug()))
def test_catalog_asset_validates(asset_slug: str):
    asset = catalog_assets_by_slug()[asset_slug]
    # Structural publish schema + binding gate for all seeded assets.
    validated = validate_asset_payload(
        asset_type=asset.asset_type,
        config=asset.config,
        install_variables=asset.install_variables,
        required_connectors=asset.required_connectors,
        publish=True,
        enforce_bindings=True,
    )
    assert validated["config"]


def test_msp_enrichment_install_ready_bindings_pass():
    from app.marketplace.install_ready import evaluate_binding_install_ready

    asset = catalog_assets_by_slug()["msp-prospects-clay-hubspot-enrichment"]
    ready = evaluate_binding_install_ready(
        {
            "slug": asset.slug,
            "asset_type": asset.asset_type,
            "config": asset.config,
            "install_variables": asset.install_variables,
        }
    )
    assert ready["installReady"] is True
    assert ready["installReadyErrors"] == []


@pytest.mark.parametrize("asset_slug", sorted(_REMEDIATED_BINDING_SLUGS))
def test_remediated_packs_are_install_ready(asset_slug: str):
    from app.marketplace.install_ready import evaluate_binding_install_ready

    asset = catalog_assets_by_slug()[asset_slug]
    ready = evaluate_binding_install_ready(
        {
            "slug": asset.slug,
            "asset_type": asset.asset_type,
            "config": asset.config,
            "install_variables": asset.install_variables,
        }
    )
    assert ready["installReady"] is True, ready.get("installReadyErrors")
    assert ready["installReadyErrors"] == []

def test_department_pack_children_exist():
    by_slug = catalog_assets_by_slug()
    for asset in list_catalog_assets():
        if asset.asset_type not in {"department_pack", "outcome_pack"}:
            continue
        for child_slug in asset.pack_children:
            assert child_slug in by_slug, f"{asset.slug} missing child {child_slug}"


def test_legacy_pack_slug_map_targets_catalog():
    by_slug = catalog_assets_by_slug()
    for legacy_id, mapped_slug in LEGACY_PACK_SLUG_MAP.items():
        assert mapped_slug in by_slug, f"legacy {legacy_id} maps to missing slug {mapped_slug}"
    assert LEGACY_PACK_SLUG_MAP["support-ops"] == "support-operations-pack"


def test_marketing_operations_pack_four_agent_handoff_chain():
    pack = catalog_assets_by_slug()["marketing-operations-pack"]
    assert pack.asset_type == "department_pack"
    assert len(pack.config["agents"]) == 4
    slugs = {agent["config"]["marketplaceSlug"] for agent in pack.config["agents"]}
    assert slugs == {
        "product-icp-strategist",
        "content-writer",
        "marketing-designer",
        "marketing-ops-coordinator",
    }
    handoff_steps = [
        step
        for step in pack.config["workflow_steps"]
        if step.get("metadata", {}).get("next_agent_seed")
    ]
    assert len(handoff_steps) == 2
    assert handoff_steps[0]["metadata"]["next_agent_seed"] == "agent:content-writer"
    assert handoff_steps[1]["metadata"]["next_agent_seed"] == "agent:marketing-ops-coordinator"


def test_support_operations_pack_tier1_zendesk_triage():
    pack = catalog_assets_by_slug()["support-operations-pack"]
    assert pack.asset_type == "department_pack"
    assert pack.pack_tier == 1
    assert pack.price_cents == 4900
    assert pack.pricing_type == "paid"
    assert {c["connectorType"] for c in pack.required_connectors} == {"zendesk"}
    assert pack.pack_children == [
        "ticket-triage",
        "zendesk-ticket-triage",
        "support-operations-knowledge",
        "sla-breach-escalation",
    ]
    assert len(pack.config["agents"]) == 1
    assert pack.config["agents"][0]["config"]["marketplaceSlug"] == "ticket-triage"
    lookup = next(
        step
        for step in pack.config["workflow_steps"]
        if (step.get("config") or {}).get("action") == "zendesk.tickets.get"
    )
    assert lookup["requires_connector"] == "zendesk"
    assert LEGACY_PACK_SLUG_MAP["support-ops"] == pack.slug


def test_msp_service_desk_3_is_complete_marketplace3_outcome_pack():
    pack = catalog_assets_by_slug()["msp-service-desk-3"]
    assert pack.asset_type == "outcome_pack"
    assert pack.category == "outcome_pack"
    assert pack.pack_tier == 3
    assert pack.pricing_type == "paid"
    assert pack.price_cents == 24900
    assert pack.config["marketplace_version"] == "3.0"

    assert len(pack.config["agents"]) == 3
    assert {agent["config"]["marketplaceSlug"] for agent in pack.config["agents"]} == {
        "msp-service-desk-coordinator",
        "msp-resolution-specialist",
        "msp-service-optimizer",
    }

    plays = pack.config["plays"]
    assert len(plays) == 8
    assert {play["key"] for play in plays} == {
        "intelligent-ticket-intake",
        "resolution-copilot",
        "sla-rescue",
        "stale-ticket-recovery",
        "recurring-problem-hunter",
        "client-communication-manager",
        "knowledge-gap-miner",
        "service-desk-optimization-review",
    }
    for play in plays:
        assert play["outcome_events"]
        assert play["kpi_keys"]
        assert play["verification"]["mode"] == "source_of_record"

    outcome = pack.config["outcome_contract"]
    assert outcome["verification_required"] is True
    assert len(outcome["outcome_events"]) == 8
    assert len(outcome["kpis"]) == 10

    dataset = pack.config["dataset"]
    assert {entity["name"] for entity in dataset["entities"]} >= {
        "tickets",
        "clients",
        "assets",
        "ticket_events",
        "play_runs",
    }
    assert len(dataset["metrics"]) == 10

    dashboard = pack.config["dashboard"]
    assert dashboard["title"] == "MSP Service Desk Outcomes"
    assert len(dashboard["metrics"]) == 8

    alternatives = pack.config["connector_alternatives"]
    assert {"halopsa", "autotask", "connectwise", "syncro", "servicenow", "freshservice", "zendesk"} == set(alternatives[0])
    assert {"intune", "jumpcloud", "jamf_pro"} == set(alternatives[1])
    assert {"huntress", "sentinelone", "crowdstrike", "connectsecure"} == set(alternatives[2])


def test_msp_service_desk_3_children_are_first_class_marketplace_assets():
    by_slug = catalog_assets_by_slug()
    pack = by_slug["msp-service-desk-3"]
    children = [by_slug[slug] for slug in pack.pack_children]
    by_type: dict[str, int] = {}
    for child in children:
        by_type[child.asset_type] = by_type.get(child.asset_type, 0) + 1

    assert by_type == {
        "ai_agent": 3,
        "play": 8,
        "knowledge_pack": 1,
        "dataset_pack": 1,
        "dashboard_pack": 1,
    }


def test_msp_service_desk_3_play_assets_match_embedded_pack_plays():
    by_slug = catalog_assets_by_slug()
    pack = by_slug["msp-service-desk-3"]
    embedded = {play["key"]: play for play in pack.config["plays"]}
    play_assets = [
        asset
        for asset in by_slug.values()
        if asset.asset_type == "play" and "msp" in asset.tags and "service-desk" in asset.tags
    ]
    assert len(play_assets) == 8
    for asset in play_assets:
        assert asset.config == embedded[asset.config["key"]]


def test_msp_service_desk_3_publishes_under_marketplace3_schema():
    pack = catalog_assets_by_slug()["msp-service-desk-3"]
    validated = validate_asset_payload(
        asset_type=pack.asset_type,
        config=pack.config,
        install_variables=pack.install_variables,
        required_connectors=pack.required_connectors,
        publish=True,
        enforce_bindings=True,
    )
    assert validated["config"]["marketplace_version"] == "3.0"
    assert len(validated["config"]["plays"]) == 8
