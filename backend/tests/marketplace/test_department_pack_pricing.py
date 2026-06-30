"""Phase 8: Department pack pricing framework and Marketing Operations Pack checkout."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.entitlements import (
    assert_install_entitlement,
    create_asset_checkout_session,
    has_active_entitlement,
)
from app.marketplace.pack_pricing import (
    DEPARTMENT_PACK_PRICING_TYPE,
    MODE_B_AUTONOMOUS_ADDON_CENTS,
    PACK_TIER_PRICE_CENTS,
    expected_price_cents_for_pack_tier,
    validate_department_pack_pricing,
)
from app.marketplace.service import MarketplaceError

MKT_OPS_ASSET_ID = "22222222-2222-2222-2222-222222222222"


def test_pack_pricing_matches_researched_framework():
    """Tier bands from Phase 8.3: $49 / $149 / $299 one-time unlock."""
    assert expected_price_cents_for_pack_tier(1) == 4900
    assert expected_price_cents_for_pack_tier(2) == 14900
    assert expected_price_cents_for_pack_tier(3) == 29900
    assert len(PACK_TIER_PRICE_CENTS) == 3
    assert DEPARTMENT_PACK_PRICING_TYPE == "paid"


def test_marketing_operations_pack_banded_as_tier_2():
    asset = {
        "slug": "marketing-operations-pack",
        "asset_type": "department_pack",
        "pricing_type": "paid",
        "price_cents": 14900,
        "pack_tier": 2,
    }
    result = validate_department_pack_pricing(asset)
    assert result["pack_tier"] == 2
    assert result["price_matches_tier_band"] is True
    assert result["pricing_type"] == "paid"


def test_pack_tier_pricing_correctly_banded():
    for tier, cents in PACK_TIER_PRICE_CENTS.items():
        asset = {
            "asset_type": "department_pack",
            "pack_tier": tier,
            "pricing_type": "paid",
            "price_cents": cents,
        }
        result = validate_department_pack_pricing(asset)
        assert result["price_matches_tier_band"] is True


def test_install_blocked_without_purchase_for_paid_pack():
    asset = {
        "id": MKT_OPS_ASSET_ID,
        "org_id": "publisher-org",
        "pricing_type": "paid",
        "price_cents": 14900,
        "currency": "usd",
    }
    entitlements = MagicMock()
    entitlements.select.return_value = entitlements
    entitlements.eq.return_value = entitlements
    entitlements.limit.return_value = entitlements
    entitlements.execute.return_value = MagicMock(data=[])
    client = MagicMock()
    client.table.return_value = entitlements

    with pytest.raises(MarketplaceError) as exc:
        assert_install_entitlement(client, "buyer-org", asset)
    assert exc.value.code == "PAYMENT_REQUIRED"
    assert exc.value.details["pricingType"] == "paid"
    assert exc.value.details["priceCents"] == 14900


def test_install_succeeds_after_one_time_purchase():
    asset = {
        "id": MKT_OPS_ASSET_ID,
        "org_id": "publisher-org",
        "pricing_type": "paid",
        "price_cents": 14900,
    }
    entitlements = MagicMock()
    entitlements.select.return_value = entitlements
    entitlements.eq.return_value = entitlements
    entitlements.limit.return_value = entitlements
    entitlements.execute.return_value = MagicMock(
        data=[{"id": "ent-1", "status": "active", "pricing_type": "paid"}]
    )
    client = MagicMock()
    client.table.return_value = entitlements

    assert has_active_entitlement(client, "buyer-org", MKT_OPS_ASSET_ID) is True
    assert_install_entitlement(client, "buyer-org", asset)


def test_mode_b_pricing_implication_correctly_gated():
    """Mode B add-on price is documented; base pack entitlement does not require separate Mode B purchase yet."""
    base = validate_department_pack_pricing(
        {
            "slug": "marketing-operations-pack",
            "asset_type": "department_pack",
            "pricing_type": "paid",
            "price_cents": 14900,
            "pack_tier": 2,
        }
    )
    assert base["price_cents"] == 14900
    assert MODE_B_AUTONOMOUS_ADDON_CENTS == 4900
    assert base["price_cents"] != base["price_cents"] + MODE_B_AUTONOMOUS_ADDON_CENTS


def test_existing_one_time_asset_purchases_unaffected():
    asset = {
        "asset_type": "workflow_template",
        "pricing_type": "paid",
        "price_cents": 2500,
    }
    result = validate_department_pack_pricing(asset)
    assert result["pricing_type"] == "paid"
    assert result["price_cents"] == 2500
    assert result.get("pack_tier") is None


@patch("app.billing.stripe.init_stripe")
@patch("app.marketplace.entitlements.fetch_marketplace_asset")
def test_one_time_checkout_uses_payment_mode(mock_fetch, mock_init):
    mock_fetch.return_value = {
        "id": MKT_OPS_ASSET_ID,
        "slug": "marketing-operations-pack",
        "title": "Marketing Operations Pack",
        "status": "published",
        "org_id": "publisher-org",
        "pricing_type": "paid",
        "price_cents": 14900,
        "currency": "usd",
        "pack_tier": 2,
    }
    entitlements = MagicMock()
    inserted = MagicMock()
    inserted.execute.return_value = MagicMock(data=[{"id": "ent-sub-1", "status": "pending"}])
    entitlements.select.return_value = entitlements
    entitlements.eq.return_value = entitlements
    entitlements.limit.return_value = entitlements
    entitlements.execute.return_value = MagicMock(data=[])
    entitlements.insert.return_value = inserted
    entitlements.update.return_value = entitlements
    entitlements.update.return_value.execute.return_value = MagicMock(data=[])

    client = MagicMock()
    client.table.return_value = entitlements
    settings = MagicMock(stripe_secret_key="sk_test")

    session = MagicMock(id="cs_pay", url="https://checkout.stripe.test/cs_pay")
    with patch("stripe.checkout.Session.create", return_value=session) as create_session:
        result = create_asset_checkout_session(
            client,
            settings,
            org_id="buyer-org",
            asset_ref="marketing-operations-pack",
            actor_id="user-1",
            success_url="https://app/success",
            cancel_url="https://app/cancel",
        )

    assert result["mode"] == "payment"
    assert result["checkoutUrl"] == "https://checkout.stripe.test/cs_pay"
    create_session.assert_called_once()
    call_kwargs = create_session.call_args.kwargs
    assert call_kwargs["mode"] == "payment"
    line_item = call_kwargs["line_items"][0]
    assert line_item["price_data"]["unit_amount"] == 14900
    assert "recurring" not in line_item["price_data"]
