"""Unit tests for marketplace browse service (MKT-5.1)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.marketplace.browse import (
    MarketplaceBrowseError,
    get_marketplace_asset,
    is_uuid,
    list_marketplace_assets,
)


def _table(select_data: list | None = None, count: int | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.or_.return_value = mock
    mock.order.return_value = mock
    mock.range.return_value = mock
    mock.in_.return_value = mock
    mock.limit.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [], count=count)
    return mock


ASSET_ROW = {
    "id": "11111111-1111-1111-1111-111111111111",
    "slug": "marketing-analyst",
    "title": "Marketing Analyst",
    "description": "Starter agent",
    "asset_type": "ai_agent",
    "category": "ai_agent",
    "department": "Marketing",
    "tags": ["marketing"],
    "visibility": "public",
    "status": "published",
    "pricing_type": "free",
    "price_cents": 0,
    "currency": "usd",
    "required_connectors": [{"connectorType": "hubspot", "label": "HubSpot", "required": True}],
    "install_count": 0,
    "clone_count": 0,
    "average_rating": None,
    "review_count": 0,
    "current_version": 1,
    "published_at": "2026-06-17T00:00:00+00:00",
    "publisher_id": "pub-1",
    "org_id": None,
    "business_outcome": "Reduce manual reporting time.",
    "use_case": "Weekly marketing review",
    "estimated_hours_saved": 4.0,
    "featured": False,
    "verified": False,
    "config": {"name": "Marketing Analyst"},
    "install_variables": [],
    "required_permissions": [],
    "cloned_from_asset_id": None,
    "created_at": "2026-06-17T00:00:00+00:00",
    "updated_at": "2026-06-17T00:00:00+00:00",
}


def test_is_uuid():
    assert is_uuid("11111111-1111-1111-1111-111111111111") is True
    assert is_uuid("marketing-analyst") is False


def test_list_marketplace_assets_serializes_summary():
    assets = _table([ASSET_ROW], count=1)
    installs = _table([])
    entitlements = _table([])
    connectors = _table([{"type": "hubspot"}])
    client = MagicMock()

    def table(name):
        if name == "marketplace_assets":
            return assets
        if name == "marketplace_installs":
            return installs
        if name == "marketplace_asset_entitlements":
            return entitlements
        if name == "connectors":
            return connectors
        return _table([])

    client.table.side_effect = table
    result = list_marketplace_assets(client, "org-1")
    assert result["total"] == 1
    assert result["assets"][0]["slug"] == "marketing-analyst"
    assert result["assets"][0]["canInstall"] is True
    assert result["assets"][0]["requiresPayment"] is False
    assert result["assets"][0]["hasEntitlement"] is False
    assert result["assets"][0]["businessOutcome"] == "Reduce manual reporting time."
    assert result["assets"][0]["useCase"] == "Weekly marketing review"
    assert result["assets"][0]["estimatedHoursSaved"] == 4.0


def test_list_marketplace_assets_featured_filter():
    assets = _table([{**ASSET_ROW, "featured": True}], count=1)
    installs = _table([])
    entitlements = _table([])
    connectors = _table([{"type": "hubspot"}])
    client = MagicMock()

    def table(name):
        if name == "marketplace_assets":
            return assets
        if name == "marketplace_installs":
            return installs
        if name == "marketplace_asset_entitlements":
            return entitlements
        if name == "connectors":
            return connectors
        return _table([])

    client.table.side_effect = table
    result = list_marketplace_assets(client, "org-1", featured=True)
    assert result["total"] == 1
    assert result["assets"][0]["featured"] is True
    assets.eq.assert_any_call("featured", True)


def test_get_marketplace_asset_by_slug():
    assets = _table([ASSET_ROW])
    installs = _table([])
    entitlements = _table([])
    connectors = _table([])
    client = MagicMock()

    def table(name):
        if name == "marketplace_assets":
            return assets
        if name == "marketplace_installs":
            return installs
        if name == "marketplace_asset_entitlements":
            return entitlements
        if name == "connectors":
            return connectors
        return _table([])

    client.table.side_effect = table
    result = get_marketplace_asset(client, "org-1", "marketing-analyst")
    assert result["asset"]["slug"] == "marketing-analyst"
    assert result["asset"]["config"]["name"] == "Marketing Analyst"


def test_get_marketplace_asset_not_found():
    assets = _table([])
    client = MagicMock()
    client.table.side_effect = lambda name: assets if name == "marketplace_assets" else _table([])
    with pytest.raises(MarketplaceBrowseError) as exc:
        get_marketplace_asset(client, "org-1", "missing")
    assert exc.value.code == "NOT_FOUND"


def test_list_invalid_asset_type():
    client = MagicMock()
    with pytest.raises(MarketplaceBrowseError) as exc:
        list_marketplace_assets(client, "org-1", asset_type="invalid")
    assert exc.value.code == "VALIDATION_ERROR"
