"""Regression coverage for Stripe-owned billing status and plan-only offers."""
from unittest.mock import MagicMock

import pytest

from app.routers import billing
from app.routers.webhooks import stripe as webhook


def test_founder_discount_targets_base_plan_products_only(monkeypatch):
    settings = MagicMock()
    monkeypatch.setattr(billing, "init_stripe", lambda _settings: None)
    monkeypatch.setattr(
        billing, "price_id_for_plan",
        lambda _settings, plan, billing_interval: f"price_{plan}_{billing_interval}",
    )
    price_products = {
        "price_node_monthly": "prod_node",
        "price_node_annual": "prod_node",
        "price_control_monthly": "prod_control",
        "price_control_annual": "prod_control",
        "price_command_monthly": "prod_command",
        "price_command_annual": "prod_command",
    }
    retrieve = MagicMock(side_effect=lambda price_id: {"product": price_products[price_id]})
    monkeypatch.setattr(billing.stripe.Price, "retrieve", retrieve)

    assert billing._founder_discount_base_products(settings) == [
        "prod_command", "prod_control", "prod_node",
    ]
    assert retrieve.call_count == 6


def test_missing_base_plan_price_fails_closed(monkeypatch):
    monkeypatch.setattr(billing, "init_stripe", lambda _settings: None)
    monkeypatch.setattr(billing, "price_id_for_plan", lambda *_args, **_kwargs: None)
    with pytest.raises(Exception) as exc:
        billing._founder_discount_base_products(MagicMock())
    assert getattr(exc.value, "status_code", None) == 503


@pytest.mark.parametrize("event_type", ["invoice.payment_succeeded", "invoice.payment_failed"])
def test_invoice_events_never_override_stripe_subscription_status(monkeypatch, event_type):
    client = MagicMock()
    monkeypatch.setattr(webhook, "_write_event", MagicMock())
    webhook._apply_stripe_event(
        client, MagicMock(), event_type,
        {"id": "in_1", "customer": "cus_1", "subscription": "sub_expired"},
        {"org_id": "org_1"}, "org_1", {"id": "evt_1", "type": event_type},
    )
    client.table.assert_not_called()
    webhook._write_event.assert_called_once()
