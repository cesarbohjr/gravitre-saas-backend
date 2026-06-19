"""MKT-AUDIT-13.1: Federated partner registry browse and connector_config sync."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.convergence import (
    MarketplaceConvergenceError,
    _serialize_federated_connector,
    link_asset_to_registry,
    list_federated_connector_assets,
    upsert_connector_asset_from_registry,
)


def _chain_table(*, execute_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.limit.return_value = mock
    mock.update.return_value = mock
    mock.insert.return_value = mock
    mock.execute.return_value = MagicMock(data=execute_data or [])
    return mock


REGISTRY_ROW = {
    "id": "reg-1",
    "vendor": "acme",
    "name": "Acme Tools",
    "description": "Demo connector",
    "version": "1.0.0",
    "authType": "apiKey",
    "status": "published",
    "manifest": {"description": "From manifest"},
}


def test_serialize_federated_connector_maps_pricing():
    row = _serialize_federated_connector(
        REGISTRY_ROW,
        pricing={"model": "flat_monthly", "priceCents": 1500, "currency": "usd"},
    )
    assert row["assetType"] == "connector_config"
    assert row["source"] == "partner_registry"
    assert row["pricingType"] == "subscription"
    assert row["priceCents"] == 1500
    assert row["federated"] is True


@patch("app.marketplace.convergence.enrich_registry_with_pricing")
@patch("app.marketplace.convergence.list_registry")
def test_list_federated_connector_assets(mock_list, mock_enrich):
    mock_list.return_value = [{"id": "reg-1", "vendor": "acme", "name": "Acme Tools", "description": ""}]
    mock_enrich.return_value = [
        {
            "id": "reg-1",
            "vendor": "acme",
            "name": "Acme Tools",
            "description": "",
            "pricing": {"model": "free", "priceCents": 0, "currency": "usd"},
        }
    ]
    client = MagicMock()
    result = list_federated_connector_assets(client, limit=10, offset=0)
    assert result["total"] == 1
    assert result["assets"][0]["registryId"] == "reg-1"


@patch("app.marketplace.crud.resolve_org_publisher_id")
def test_upsert_connector_asset_from_registry_creates(mock_publisher):
    mock_publisher.return_value = "pub-1"
    linked = _chain_table(execute_data=[])
    by_slug = _chain_table(execute_data=[])
    insert = _chain_table(execute_data=[{"id": "asset-new"}])
    client = MagicMock()
    client.table.side_effect = [linked, by_slug, insert]

    result = upsert_connector_asset_from_registry(client, REGISTRY_ROW)
    assert result["created"] is True
    assert result["assetId"] == "asset-new"
    assert result["slug"] == "partner-acme"
    insert.insert.assert_called_once()


@patch("app.marketplace.crud.resolve_org_publisher_id")
def test_upsert_connector_asset_from_registry_updates_linked(mock_publisher):
    mock_publisher.return_value = "pub-1"
    linked = _chain_table(execute_data=[{"id": "asset-existing", "slug": "partner-acme"}])
    by_slug = _chain_table(execute_data=[])
    update = _chain_table(execute_data=[{"id": "asset-existing"}])
    client = MagicMock()
    client.table.side_effect = [linked, by_slug, update]

    result = upsert_connector_asset_from_registry(client, REGISTRY_ROW)
    assert result["created"] is False
    assert result["assetId"] == "asset-existing"
    update.update.assert_called_once()


def test_link_asset_to_registry_success():
    registry = _chain_table(execute_data=[{"id": "reg-1", "vendor": "acme", "status": "published"}])
    assets = _chain_table(execute_data=[{"id": "asset-1"}])
    client = MagicMock()
    client.table.side_effect = [registry, assets]

    result = link_asset_to_registry(client, asset_id="asset-1", registry_id="reg-1")
    assert result["assetId"] == "asset-1"
    assert result["registryId"] == "reg-1"
    assert result["vendor"] == "acme"


def test_link_asset_to_registry_requires_published_registry():
    registry = _chain_table(execute_data=[{"id": "reg-1", "status": "draft"}])
    client = MagicMock()
    client.table.return_value = registry

    with pytest.raises(MarketplaceConvergenceError) as exc:
        link_asset_to_registry(client, asset_id="asset-1", registry_id="reg-1")
    assert exc.value.code == "NOT_FOUND"


def test_link_asset_to_registry_requires_asset():
    registry = _chain_table(execute_data=[{"id": "reg-1", "vendor": "acme", "status": "published"}])
    assets = _chain_table(execute_data=[])
    client = MagicMock()
    client.table.side_effect = [registry, assets]

    with pytest.raises(MarketplaceConvergenceError) as exc:
        link_asset_to_registry(client, asset_id="asset-missing", registry_id="reg-1")
    assert exc.value.code == "NOT_FOUND"
