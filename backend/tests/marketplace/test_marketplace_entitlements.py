"""MKT-AUDIT-12.1: Paid install entitlements and checkout."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.entitlements import (
    MarketplaceEntitlementError,
    asset_requires_payment,
    assert_install_entitlement,
    create_asset_checkout_session,
    get_entitlement_status,
    has_active_entitlement,
)
from app.marketplace.service import MarketplaceError

ASSET_ID = "11111111-1111-1111-1111-111111111111"


def _table(data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.limit.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.execute.return_value = MagicMock(data=data or [])
    return mock


def test_asset_requires_payment_for_paid_public_asset():
    asset = {
        "id": ASSET_ID,
        "org_id": "publisher-org",
        "pricing_type": "paid",
        "price_cents": 2500,
    }
    assert asset_requires_payment(asset, org_id="buyer-org") is True
    assert asset_requires_payment(asset, org_id="publisher-org") is False


def test_assert_install_entitlement_blocks_without_purchase():
    asset = {
        "id": ASSET_ID,
        "org_id": "publisher-org",
        "pricing_type": "paid",
        "price_cents": 9900,
        "currency": "usd",
    }
    entitlements = _table([])
    client = MagicMock()
    client.table.side_effect = lambda name: entitlements if name == "marketplace_asset_entitlements" else _table([])

    with pytest.raises(MarketplaceError) as exc:
        assert_install_entitlement(client, "buyer-org", asset)
    assert exc.value.code == "PAYMENT_REQUIRED"


def test_has_active_entitlement_true():
    entitlements = _table([{"id": "ent-1", "status": "active"}])
    client = MagicMock()
    client.table.return_value = entitlements
    assert has_active_entitlement(client, "org-1", ASSET_ID) is True


def test_get_entitlement_status_free_asset():
    asset = {"id": ASSET_ID, "pricing_type": "free", "price_cents": 0}
    client = MagicMock()
    client.table.return_value = _table([])
    status = get_entitlement_status(client, "org-1", asset)
    assert status["requiresPayment"] is False
    assert status["hasEntitlement"] is False


@patch("app.marketplace.entitlements.fetch_marketplace_asset")
def test_create_checkout_rejects_free_asset(mock_fetch):
    mock_fetch.return_value = {
        "id": ASSET_ID,
        "status": "published",
        "org_id": "publisher-org",
        "pricing_type": "free",
        "price_cents": 0,
    }
    client = MagicMock()
    settings = MagicMock(stripe_secret_key="sk_test")
    with pytest.raises(MarketplaceEntitlementError) as exc:
        create_asset_checkout_session(
            client,
            settings,
            org_id="buyer-org",
            asset_ref=ASSET_ID,
            actor_id="user-1",
            success_url="https://app/success",
            cancel_url="https://app/cancel",
        )
    assert exc.value.code == "FREE_ASSET"
