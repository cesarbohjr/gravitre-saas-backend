"""MKT-AUDIT-11.3: Featured and verified asset flags."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.flags import (
    MarketplaceFlagsError,
    list_platform_public_catalog,
    set_asset_featured,
    set_asset_pricing,
    set_asset_verified,
)

ORG_ID = "org-11111111-1111-1111-1111-111111111111"


def _asset(**overrides):
    row = {
        "id": "asset-1",
        "slug": "sales-pack",
        "title": "Sales Pack",
        "asset_type": "department_pack",
        "status": "published",
        "visibility": "public",
        "org_id": ORG_ID,
        "config": {},
        "required_connectors": [],
        "install_variables": [],
        "current_version": 1,
        "featured": False,
        "verified": False,
    }
    row.update(overrides)
    return row


@patch("app.marketplace.flags.write_audit_event")
@patch("app.marketplace.flags._fetch_asset")
def test_set_asset_featured(mock_fetch, mock_audit):
    mock_fetch.side_effect = [_asset(), _asset(featured=True)]
    assets = MagicMock()
    assets.update.return_value = assets
    assets.eq.return_value = assets
    assets.execute.return_value = MagicMock(data=[{"id": "asset-1"}])
    client = MagicMock()
    client.table.return_value = assets

    result = set_asset_featured(
        client,
        "sales-pack",
        featured=True,
        actor_id="platform-1",
        org_id=ORG_ID,
    )
    assert result["featured"] is True
    mock_audit.assert_called_once()


@patch("app.marketplace.flags._fetch_asset")
def test_set_asset_featured_requires_public_published(mock_fetch):
    mock_fetch.return_value = _asset(visibility="internal")
    client = MagicMock()
    with pytest.raises(MarketplaceFlagsError):
        set_asset_featured(client, "sales-pack", featured=True, actor_id="platform-1")


@patch("app.marketplace.flags._fetch_asset")
def test_set_asset_verified_requires_published(mock_fetch):
    mock_fetch.return_value = _asset(status="draft")
    client = MagicMock()
    with pytest.raises(MarketplaceFlagsError):
        set_asset_verified(client, "sales-pack", verified=True, actor_id="platform-1")


@patch("app.marketplace.flags._serialize_asset")
def test_list_platform_public_catalog(mock_serialize):
    assets = MagicMock()
    assets.select.return_value = assets
    assets.eq.return_value = assets
    assets.order.return_value = assets
    assets.range.return_value = assets
    assets.execute.return_value = MagicMock(
        data=[_asset(featured=True, verified=True)],
        count=1,
    )
    client = MagicMock()
    client.table.return_value = assets
    mock_serialize.return_value = {"slug": "sales-pack", "featured": True, "verified": True}

    result = list_platform_public_catalog(client, featured=True, limit=10)
    assert result["total"] == 1
    assert len(result["assets"]) == 1
    assets.eq.assert_any_call("featured", True)


@patch("app.marketplace.flags.write_audit_event")
@patch("app.marketplace.flags._fetch_asset")
def test_set_asset_verified(mock_fetch, mock_audit):
    mock_fetch.side_effect = [_asset(), _asset(verified=True)]
    assets = MagicMock()
    assets.update.return_value = assets
    assets.eq.return_value = assets
    assets.execute.return_value = MagicMock(data=[{"id": "asset-1"}])
    client = MagicMock()
    client.table.return_value = assets

    result = set_asset_verified(
        client,
        "sales-pack",
        verified=True,
        actor_id="platform-1",
        org_id=ORG_ID,
    )
    assert result["verified"] is True


@patch("app.marketplace.flags.write_audit_event")
@patch("app.marketplace.flags._fetch_asset")
def test_set_asset_pricing_on_public_published(mock_fetch, mock_audit):
    mock_fetch.side_effect = [
        _asset(pricing_type="free", price_cents=0),
        _asset(pricing_type="paid", price_cents=499),
    ]
    assets = MagicMock()
    assets.update.return_value = assets
    assets.eq.return_value = assets
    assets.execute.return_value = MagicMock(data=[{"id": "asset-1"}])
    client = MagicMock()
    client.table.return_value = assets

    result = set_asset_pricing(
        client,
        "sales-pack",
        pricing_type="paid",
        price_cents=499,
        actor_id="platform-1",
        org_id=ORG_ID,
    )
    assert result["updated"] is True
    assert result["asset"]["priceCents"] == 499
    mock_audit.assert_called_once()


@patch("app.marketplace.flags._fetch_asset")
def test_set_asset_pricing_rejects_internal_published(mock_fetch):
    mock_fetch.return_value = _asset(visibility="internal", status="published")
    client = MagicMock()
    with pytest.raises(MarketplaceFlagsError):
        set_asset_pricing(
            client,
            "sales-pack",
            pricing_type="paid",
            price_cents=499,
            actor_id="platform-1",
        )


@patch("app.marketplace.flags.write_audit_event")
@patch("app.marketplace.flags.set_asset_pricing")
@patch("app.marketplace.crud._assert_org_owns_asset")
@patch("app.marketplace.crud._fetch_asset")
def test_set_org_asset_pricing_delegates_with_ownership(mock_fetch, mock_assert, mock_set, mock_audit):
    mock_fetch.return_value = {"id": "asset-1", "org_id": ORG_ID}
    mock_set.return_value = {"updated": True, "asset": {"slug": "sales-pack"}}

    from app.marketplace.flags import set_org_asset_pricing

    result = set_org_asset_pricing(
        object(),
        ORG_ID,
        "sales-pack",
        pricing_type="paid",
        price_cents=499,
        actor_id="user-1",
    )
    assert result["updated"] is True
    mock_assert.assert_called_once()
    mock_set.assert_called_once()
