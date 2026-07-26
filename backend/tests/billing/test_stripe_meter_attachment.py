"""Tests for Stripe metered price attachment utility and admin endpoints."""
from __future__ import annotations

from unittest.mock import MagicMock

import asyncio

import pytest
import stripe

from app.billing.stripe_metering import StripeAttachmentError, attach_metered_price_to_subscription
from app.config import Settings
from app.routers import billing_sync


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        supabase_jwt_secret="jwt",
        openai_api_key="sk-test",
        stripe_secret_key="sk_test_123",
        stripe_metered_price_id_node="price_metered_node",
    )
    base.update(overrides)
    return Settings(**base)


def test_attach_when_not_present(monkeypatch):
    item = MagicMock()
    item.id = "price_metered_node"
    item.price.id = "price_flat"
    sub = MagicMock()
    sub.items.data = [item]
    monkeypatch.setattr(stripe.Subscription, "retrieve", lambda sid: sub)
    created = MagicMock(id="si_metered")
    monkeypatch.setattr(stripe.SubscriptionItem, "create", lambda **kw: created)
    result = attach_metered_price_to_subscription("org-1", "sub_1", "node", _settings())
    assert result == {"status": "attached", "item_id": "si_metered"}


def test_idempotent_already_attached(monkeypatch):
    item = MagicMock()
    item.id = "si_existing"
    item.price.id = "price_metered_node"
    sub = MagicMock()
    sub.items.data = [item]
    monkeypatch.setattr(stripe.Subscription, "retrieve", lambda sid: sub)
    called = {"create": False}
    monkeypatch.setattr(
        stripe.SubscriptionItem,
        "create",
        lambda **kw: called.update(create=True) or MagicMock(),
    )
    result = attach_metered_price_to_subscription("org-1", "sub_1", "node", _settings())
    assert result["status"] == "already_attached"
    assert called["create"] is False


def test_missing_metered_price_raises():
    with pytest.raises(StripeAttachmentError, match="No metered price configured"):
        attach_metered_price_to_subscription("org-1", "sub_1", "control", _settings(stripe_metered_price_id_control=""))


def test_dry_run_no_stripe_calls(monkeypatch):
    called = {"retrieve": False}

    def _retrieve(_sid):
        called["retrieve"] = True
        return MagicMock()

    monkeypatch.setattr(stripe.Subscription, "retrieve", _retrieve)
    monkeypatch.setattr(
        billing_sync,
        "_lookup_org_subscription",
        lambda client, org_id: {
            "stripe_subscription_id": "sub_1",
            "plan_code": "node",
        },
    )
    result = billing_sync._attach_plan_for_org(_settings(), "org-1", dry_run=True)
    assert result["ai_credits"]["action"] == "would_attach"
    assert called["retrieve"] is False


def test_bulk_counts(monkeypatch):
    monkeypatch.setattr(
        billing_sync,
        "_attach_plan_for_org",
        lambda settings, org_id, dry_run=True: {
            "org_id": org_id,
            "ai_credits": {"action": "would_attach"},
            "research_lookups": {"action": "would_attach"},
        },
    )
    monkeypatch.setattr(
        billing_sync,
        "get_supabase_client",
        lambda settings: MagicMock(
            table=lambda name: MagicMock(
                select=lambda *a: MagicMock(
                    eq=lambda *a: MagicMock(
                        execute=lambda: MagicMock(data=[{"org_id": "o1"}, {"org_id": "o2"}])
                    )
                )
            )
        ),
    )
    async def _noop_sleep(*_):
        return None

    monkeypatch.setattr(billing_sync.asyncio, "sleep", _noop_sleep)

    async def _run():
        return await billing_sync.attach_all_metered_prices_admin(
            billing_sync.AttachAllMeteredPricesRequest(dry_run=True),
            ({}, "admin-org"),
            _settings(),
        )

    summary = asyncio.run(_run())
    assert summary["total"] == 2
    assert summary["attached"] == 4
    assert summary["failed"] == 0
