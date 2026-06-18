"""MKT-AUDIT-13.1: Federated partner registry browse."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.marketplace.convergence import _serialize_federated_connector, list_federated_connector_assets


def test_serialize_federated_connector_maps_pricing():
    row = _serialize_federated_connector(
        {
            "id": "reg-1",
            "vendor": "acme",
            "name": "Acme Tools",
            "description": "Demo connector",
            "version": "1.0.0",
            "authType": "apiKey",
        },
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
