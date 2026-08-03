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
    assert by_type["ai_agent"] == 20
    assert by_type["workflow"] == 20
    assert by_type["knowledge_pack"] == 14
    assert by_type["department_pack"] == 6
    # 8 original packs + AI Search + Finance + HR Talent + Platform Health
    assert by_type.get("intelligence_pack", 0) == 12
    assert len(assets) == 72


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
        if asset.asset_type != "department_pack":
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
