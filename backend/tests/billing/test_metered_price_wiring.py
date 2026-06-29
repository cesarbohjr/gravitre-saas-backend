"""Tests for metered-price wiring into subscription/checkout creation."""
from __future__ import annotations

from unittest.mock import MagicMock

import stripe

from app.billing.stripe import (
    create_checkout_session,
    create_subscription_for_payment_element,
    metered_price_id_for_plan,
)
from app.config import Settings
from app.services.stripe_service import create_subscription


def _settings(metered: bool, **overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
        stripe_secret_key="sk_test_123",
        stripe_price_id_node_monthly="price_node_flat",
    )
    if metered:
        base["stripe_metered_price_id_node"] = "price_node_metered"
    base.update(overrides)
    return Settings(**base)


def test_metered_price_id_for_plan_mapping():
    s = _settings(metered=True)
    assert metered_price_id_for_plan(s, "node") == "price_node_metered"
    assert metered_price_id_for_plan(s, "starter") == "price_node_metered"  # alias -> node
    assert metered_price_id_for_plan(s, "control") is None
    assert metered_price_id_for_plan(_settings(metered=False), "node") is None


def test_checkout_includes_metered_item_when_configured(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        stripe.checkout.Session, "create", lambda **kw: captured.update(kw) or MagicMock()
    )
    create_checkout_session(
        _settings(metered=True), "cus_1", "price_node_flat", "http://ok", "http://cancel", {"org_id": "o1"}
    )
    prices = [li.get("price") for li in captured["line_items"]]
    assert prices == ["price_node_flat", "price_node_metered"]
    # metered item carries no quantity
    metered_item = next(li for li in captured["line_items"] if li["price"] == "price_node_metered")
    assert "quantity" not in metered_item


def test_checkout_flat_only_when_not_configured(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        stripe.checkout.Session, "create", lambda **kw: captured.update(kw) or MagicMock()
    )
    create_checkout_session(
        _settings(metered=False), "cus_1", "price_node_flat", "http://ok", "http://cancel", {}
    )
    assert [li["price"] for li in captured["line_items"]] == ["price_node_flat"]


def test_subscription_includes_metered_item_when_configured(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        stripe.Subscription, "create", lambda **kw: captured.update(kw) or {}
    )
    create_subscription("cus_1", "price_node_flat", 3, _settings(metered=True))
    items = captured["items"]
    assert items[0] == {"price": "price_node_flat", "quantity": 3}
    assert {"price": "price_node_metered"} in items


def test_payment_element_subscription_includes_metered_and_metadata(monkeypatch):
    captured = {}

    def fake_create(**kw):
        captured.update(kw)
        return {
            "id": "sub_123",
            "status": "incomplete",
            "latest_invoice": {
                "payment_intent": {"client_secret": "pi_secret_test"},
            },
        }

    monkeypatch.setattr(stripe.Subscription, "create", fake_create)
    result = create_subscription_for_payment_element(
        _settings(metered=True),
        "cus_1",
        "price_node_flat",
        {"org_id": "org_1", "plan_code": "node"},
    )
    assert captured["metadata"] == {"org_id": "org_1", "plan_code": "node"}
    assert captured["payment_behavior"] == "default_incomplete"
    prices = [item["price"] for item in captured["items"]]
    assert prices == ["price_node_flat", "price_node_metered"]
    assert result["client_secret"] == "pi_secret_test"
    assert result["subscription_id"] == "sub_123"
