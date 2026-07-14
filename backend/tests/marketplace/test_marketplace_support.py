"""Unit tests for marketplace support service (MKT-5.3)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.marketplace.support import (
    MarketplaceSupportError,
    build_install_deep_links,
    list_marketplace_categories,
    list_org_installs,
    marketplace_analytics_summary,
)


def test_build_install_deep_links_for_department_pack():
    row = {
        "installed_entity_type": "department_pack",
        "installed_entity_id": "pack-root",
        "metadata": {
            "agentIds": ["agent-1"],
            "workflowIds": ["wf-1"],
            "ragSourceIds": ["rag-1"],
            "operatorId": "op-1",
        },
    }
    links = build_install_deep_links(row)
    paths = {link["path"] for link in links}
    assert "/agents/agent-1" in paths
    assert "/workflows/wf-1" in paths
    assert "/sources/rag-1" in paths
    assert "/agents/op-1" in paths


def test_build_install_deep_links_singular_entity_ids():
    row = {
        "installed_entity_type": "agent",
        "installed_entity_id": "agent-solo",
        "metadata": {
            "agentId": "agent-solo",
            "workflowId": "wf-solo",
            "ragSourceId": "rag-solo",
        },
    }
    links = build_install_deep_links(row)
    paths = {link["path"] for link in links}
    assert "/agents/agent-solo" in paths
    assert "/workflows/wf-solo" in paths
    assert "/sources/rag-solo" in paths
    labels = {link["label"] for link in links}
    assert "Workflow" in labels
    assert "Knowledge source" in labels


def test_list_org_installs_returns_deep_links():
    install_row = {
        "id": "install-1",
        "org_id": "org-1",
        "asset_id": "asset-1",
        "asset_version": 1,
        "installed_entity_type": "workflow",
        "installed_entity_id": "wf-1",
        "install_variables": {},
        "status": "active",
        "installed_by": "user-1",
        "installed_at": "2026-06-17T00:00:00+00:00",
        "updated_at": "2026-06-17T00:00:00+00:00",
        "metadata": {},
        "marketplace_assets": {
            "id": "asset-1",
            "slug": "hubspot-lead-qualification",
            "title": "HubSpot Lead Qualification",
            "asset_type": "workflow",
            "category": "workflow",
            "department": "Sales",
        },
    }
    installs = MagicMock()
    installs.select.return_value = installs
    installs.eq.return_value = installs
    installs.order.return_value = installs
    installs.range.return_value = installs
    installs.execute.return_value = MagicMock(data=[install_row], count=1)

    client = MagicMock()
    client.table.side_effect = lambda name: installs if name == "marketplace_installs" else MagicMock()

    result = list_org_installs(client, "org-1")
    assert result["total"] == 1
    assert result["installs"][0]["deepLinks"][0]["path"] == "/workflows/wf-1"
    assert result["installs"][0]["asset"]["slug"] == "hubspot-lead-qualification"


def test_list_org_installs_invalid_status():
    client = MagicMock()
    with pytest.raises(MarketplaceSupportError) as exc:
        list_org_installs(client, "org-1", status="bogus")
    assert exc.value.code == "VALIDATION_ERROR"


def test_list_marketplace_categories():
    assets = MagicMock()
    assets.select.return_value = assets
    assets.eq.return_value = assets
    assets.or_.return_value = assets
    assets.execute.return_value = MagicMock(
        data=[
            {"category": "ai_agent", "department": "Marketing", "asset_type": "ai_agent"},
            {"category": "workflow", "department": "Sales", "asset_type": "workflow"},
        ]
    )
    client = MagicMock()
    client.table.side_effect = lambda name: assets if name == "marketplace_assets" else MagicMock()

    result = list_marketplace_categories(client, "org-1")
    assert result["totalAssets"] == 2
    assert result["assetTypes"][0]["key"] == "ai_agent"


def test_marketplace_analytics_summary():
    assets = MagicMock()
    assets.select.return_value = assets
    assets.eq.return_value = assets
    assets.or_.return_value = assets
    assets.execute.side_effect = [
        MagicMock(
            data=[
                {"category": "ai_agent", "department": "Marketing", "asset_type": "ai_agent"},
            ]
        ),
        MagicMock(data=[{"install_count": 3, "clone_count": 1}]),
    ]

    def make_counter(count: int) -> MagicMock:
        mock = MagicMock()
        mock.select.return_value = mock
        mock.eq.return_value = mock
        mock.execute.return_value = MagicMock(data=[{"id": "x"}] * count, count=count)
        return mock

    installs = make_counter(2)
    saves = make_counter(1)
    reviews = make_counter(1)
    adoption = MagicMock()
    adoption.select.return_value = adoption
    adoption.eq.return_value = adoption
    adoption.execute.return_value = MagicMock(data=[], count=0)

    client = MagicMock()

    def table(name):
        if name == "marketplace_assets":
            return assets
        if name == "marketplace_installs":
            return installs
        if name == "marketplace_saves":
            return saves
        if name == "marketplace_reviews":
            return reviews
        if name == "marketplace_asset_adoption_events":
            return adoption
        return MagicMock()

    client.table.side_effect = table
    result = marketplace_analytics_summary(client, "org-1")
    assert result["catalog"]["totalAssets"] == 1
    assert result["catalog"]["totalInstallCount"] == 3
    assert result["org"]["activeInstalls"] == 2
    assert result["org"]["savedAssets"] == 1
    assert result["org"]["usageEvents"] == 0
    assert result["org"]["topAssetsByUsage"] == []


def test_marketplace_analytics_summary_ranks_adoption():
    assets = MagicMock()
    assets.select.return_value = assets
    assets.eq.return_value = assets
    assets.or_.return_value = assets
    assets.execute.side_effect = [
        MagicMock(data=[{"category": "ai_agent", "department": "Sales", "asset_type": "ai_agent"}]),
        MagicMock(data=[{"install_count": 1, "clone_count": 0}]),
    ]

    def make_counter(count: int) -> MagicMock:
        mock = MagicMock()
        mock.select.return_value = mock
        mock.eq.return_value = mock
        mock.execute.return_value = MagicMock(data=[{"id": "x"}] * count, count=count)
        return mock

    adoption = MagicMock()
    adoption.select.return_value = adoption
    adoption.eq.return_value = adoption
    adoption.execute.return_value = MagicMock(
        data=[
            {
                "asset_id": "asset-1",
                "marketplace_assets": {"slug": "sales-pack", "title": "Sales Pack"},
            },
            {
                "asset_id": "asset-1",
                "marketplace_assets": {"slug": "sales-pack", "title": "Sales Pack"},
            },
            {
                "asset_id": "asset-2",
                "marketplace_assets": {"slug": "ops-pack", "title": "Ops Pack"},
            },
        ],
        count=3,
    )

    client = MagicMock()

    def table(name):
        if name == "marketplace_assets":
            return assets
        if name == "marketplace_installs":
            return make_counter(1)
        if name == "marketplace_saves":
            return make_counter(0)
        if name == "marketplace_reviews":
            return make_counter(0)
        if name == "marketplace_asset_adoption_events":
            return adoption
        return MagicMock()

    client.table.side_effect = table
    result = marketplace_analytics_summary(client, "org-1")
    assert result["org"]["usageEvents"] == 3
    assert result["org"]["topAssetsByUsage"][0]["slug"] == "sales-pack"
    assert result["org"]["topAssetsByUsage"][0]["usageEvents"] == 2
