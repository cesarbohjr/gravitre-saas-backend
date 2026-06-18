"""MKT-AUDIT-11.3: Featured and verified asset flags."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.flags import MarketplaceFlagsError, set_asset_featured, set_asset_verified

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
