"""Tests for research-lookup Stripe metered price attachment."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import stripe

from app.billing.stripe_research_lookup_metering import (
    attach_research_lookup_metered_price_to_subscription,
)
from app.billing.stripe_metering import StripeAttachmentError
from app.config import Settings


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        supabase_jwt_secret="jwt",
        openai_api_key="sk-test",
        stripe_secret_key="sk_test_123",
        stripe_research_lookup_metered_price_id="price_research_metered",
    )
    base.update(overrides)
    return Settings(**base)


def test_attach_when_not_present(monkeypatch):
    item = MagicMock()
    item.id = "si_flat"
    item.price.id = "price_flat"
    sub = MagicMock()
    sub.items.data = [item]
    monkeypatch.setattr(stripe.Subscription, "retrieve", lambda sid: sub)
    created = MagicMock(id="si_research")
    monkeypatch.setattr(stripe.SubscriptionItem, "create", lambda **kw: created)
    result = attach_research_lookup_metered_price_to_subscription("org-1", "sub_1", _settings())
    assert result["status"] == "attached"
    assert result["item_id"] == "si_research"


def test_idempotent_already_attached(monkeypatch):
    item = MagicMock()
    item.id = "si_existing"
    item.price.id = "price_research_metered"
    sub = MagicMock()
    sub.items.data = [item]
    monkeypatch.setattr(stripe.Subscription, "retrieve", lambda sid: sub)
    called = {"create": False}
    monkeypatch.setattr(
        stripe.SubscriptionItem,
        "create",
        lambda **kw: called.update(create=True) or MagicMock(),
    )
    result = attach_research_lookup_metered_price_to_subscription("org-1", "sub_1", _settings())
    assert result["status"] == "already_attached"
    assert called["create"] is False


def test_missing_price_raises():
    with pytest.raises(StripeAttachmentError, match="STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID"):
        attach_research_lookup_metered_price_to_subscription(
            "org-1", "sub_1", _settings(stripe_research_lookup_metered_price_id="")
        )
