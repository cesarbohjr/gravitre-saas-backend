"""Founder-issued promotions and four-way customer reporting tests."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.billing.commercial_offers import (
    checkout_offer_for_org,
    redeem_checkout_offer,
    segment_for_org,
)
from app.billing import stripe as stripe_billing


def _client_with_grants(grants):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = grants
    return client


def test_founder_trial_30_days():
    client = _client_with_grants([{
        "id": "a" * 36, "offer_type": "trial", "trial_days": 30,
        "stripe_coupon_id": None, "status": "available", "valid_until": None,
    }])
    assert checkout_offer_for_org(client, "org")["trial_days"] == 30


def test_founder_discount_uses_stripe_coupon():
    client = _client_with_grants([{
        "id": "b" * 36, "offer_type": "discount", "trial_days": None,
        "stripe_coupon_id": "coupon_30", "status": "available", "valid_until": None,
    }])
    assert checkout_offer_for_org(client, "org")["stripe_coupon_id"] == "coupon_30"


@pytest.mark.parametrize("grants", [
    [],
    [{"id": "1", "offer_type": "trial", "trial_days": 0, "valid_until": None}],
    [{"id": "1", "offer_type": "discount", "stripe_coupon_id": "", "valid_until": None}],
    [{"id": "1", "offer_type": "trial", "trial_days": 30,
      "valid_until": (datetime.now(timezone.utc)-timedelta(days=1)).isoformat()}],
    [{"id": "1", "offer_type": "trial", "trial_days": 30, "valid_until": None}] * 2,
])
def test_invalid_or_expired_grants_fail_closed(grants):
    assert checkout_offer_for_org(_client_with_grants(grants), "org") is None


def test_signed_checkout_redemption_conditional_update():
    client = MagicMock()
    client.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{"id": "ok"}]
    grant_id = "11111111-1111-4111-8111-111111111111"
    assert redeem_checkout_offer(client, "org", grant_id, "sub_1") is True
    assert client.table.call_args.args == ("org_promotional_grants",)
    assert client.table.return_value.update.call_args.args[0]["status"] == "redeemed"


def test_invalid_grant_id_cannot_redeem():
    client = MagicMock()
    assert redeem_checkout_offer(client, "org", "not-a-uuid", "sub_1") is False
    client.table.assert_not_called()


def test_stripe_checkout_trial_is_stripe_subscription_trial(monkeypatch):
    monkeypatch.setattr(stripe_billing, "init_stripe", lambda _: None)
    monkeypatch.setattr(stripe_billing, "_subscription_line_items", lambda *_a, **_k: [{"price": "price_1", "quantity": 1}])
    create = MagicMock(return_value={"id": "cs_test"})
    monkeypatch.setattr(stripe_billing.stripe.checkout.Session, "create", create)
    stripe_billing.create_checkout_session(
        MagicMock(), "cus_1", "price_1", "https://app/success",
        "https://app/cancel", {"org_id": "org", "plan_code": "control"},
        offer={"grant_id": "grant_1", "trial_days": 30},
    )
    args = create.call_args.kwargs
    assert args["subscription_data"]["trial_period_days"] == 30
    assert args["subscription_data"]["metadata"]["offer_grant_id"] == "grant_1"
    assert args["payment_method_collection"] == "always"
    assert "discounts" not in args


def test_stripe_checkout_discount_is_coupon_not_custom_price(monkeypatch):
    monkeypatch.setattr(stripe_billing, "init_stripe", lambda _: None)
    monkeypatch.setattr(stripe_billing, "_subscription_line_items", lambda *_a, **_k: [{"price": "price_1", "quantity": 1}])
    create = MagicMock(return_value={"id": "cs_test"})
    monkeypatch.setattr(stripe_billing.stripe.checkout.Session, "create", create)
    stripe_billing.create_checkout_session(
        MagicMock(), "cus_1", "price_1", "https://app/success",
        "https://app/cancel", {"org_id": "org", "plan_code": "control"},
        offer={"grant_id": "grant_2", "stripe_coupon_id": "coupon_30"},
    )
    args = create.call_args.kwargs
    assert args["discounts"] == [{"coupon": "coupon_30"}]
    assert "trial_period_days" not in args["subscription_data"]
    assert "allow_promotion_codes" not in args
