"""Cancel/reactivate must persist cancel_at_period_end without 500s."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.routers import billing as billing_router
from tests.billing.test_stripe_webhook_processing import _FakeClient


@pytest.mark.asyncio
async def test_cancel_at_period_end_without_stripe_subscription(monkeypatch):
    org_id = "55555555-5555-5555-5555-555555555555"
    client = _FakeClient()
    client._store["org_billing"] = [
        {
            "org_id": org_id,
            "plan_code": "node",
            "billing_status": "trialing",
            "cancel_at_period_end": False,
        }
    ]
    client._store["subscriptions"] = [
        {
            "org_id": org_id,
            "tier": "node",
            "status": "trialing",
            "seat_count": 1,
            "lite_seats": 0,
            "current_period_start": "2026-08-01T00:00:00+00:00",
            "current_period_end": "2026-08-15T00:00:00+00:00",
        }
    ]

    settings = MagicMock()
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_service_role_key = "service-role"
    settings.stripe_secret_key = ""

    monkeypatch.setattr(billing_router, "create_client", lambda *_a, **_k: client)
    monkeypatch.setattr(
        billing_router,
        "get_org_billing",
        lambda _c, oid: next(
            (r for r in client._store.get("org_billing", []) if r.get("org_id") == oid),
            None,
        ),
    )

    result = await billing_router.cancel_subscription(
        billing_router.CancelRequest(at_period_end=True),
        _admin=({"user_id": "u1"}, org_id),
        settings=settings,
    )

    assert result["cancel_at_period_end"] is True
    billing_row = client._store["org_billing"][0]
    assert billing_row["cancel_at_period_end"] is True
    sub_row = client._store["subscriptions"][0]
    assert sub_row["status"] == "active"


@pytest.mark.asyncio
async def test_cancel_at_period_end_calls_stripe_when_subscription_present(monkeypatch):
    org_id = "66666666-6666-6666-6666-666666666666"
    client = _FakeClient()
    client._store["org_billing"] = [
        {
            "org_id": org_id,
            "plan_code": "node",
            "billing_status": "active",
            "stripe_subscription_id": "sub_live",
            "cancel_at_period_end": False,
        }
    ]
    client._store["subscriptions"] = [
        {
            "org_id": org_id,
            "tier": "node",
            "status": "active",
            "stripe_subscription_id": "sub_live",
            "seat_count": 1,
            "lite_seats": 0,
        }
    ]

    settings = MagicMock()
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_service_role_key = "service-role"
    settings.stripe_secret_key = "sk_test_x"

    stripe_calls: list[tuple[str, bool]] = []

    def _fake_stripe_cancel(sub_id: str, *, immediate: bool, settings: MagicMock):
        stripe_calls.append((sub_id, immediate))
        return {"id": sub_id, "cancel_at_period_end": not immediate}

    monkeypatch.setattr(
        "app.services.stripe_service.cancel_subscription",
        _fake_stripe_cancel,
    )
    monkeypatch.setattr(billing_router, "create_client", lambda *_a, **_k: client)
    monkeypatch.setattr(
        billing_router,
        "get_org_billing",
        lambda _c, oid: next(
            (r for r in client._store.get("org_billing", []) if r.get("org_id") == oid),
            None,
        ),
    )

    result = await billing_router.cancel_subscription(
        billing_router.CancelRequest(at_period_end=True),
        _admin=({"user_id": "u1"}, org_id),
        settings=settings,
    )

    assert stripe_calls == [("sub_live", False)]
    assert result["cancel_at_period_end"] is True


@pytest.mark.asyncio
async def test_cancel_at_period_end_without_subscriptions_row(monkeypatch):
    org_id = "88888888-8888-8888-8888-888888888888"
    client = _FakeClient()
    client._store["org_billing"] = [
        {
            "org_id": org_id,
            "plan_code": "node",
            "billing_status": "trialing",
            "cancel_at_period_end": False,
            "current_period_end": "2026-08-15T00:00:00+00:00",
        }
    ]

    settings = MagicMock()
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_service_role_key = "service-role"
    settings.stripe_secret_key = ""

    monkeypatch.setattr(billing_router, "create_client", lambda *_a, **_k: client)
    monkeypatch.setattr(
        billing_router,
        "get_org_billing",
        lambda _c, oid: next(
            (r for r in client._store.get("org_billing", []) if r.get("org_id") == oid),
            None,
        ),
    )

    result = await billing_router.cancel_subscription(
        billing_router.CancelRequest(at_period_end=True),
        _admin=({"user_id": "u1"}, org_id),
        settings=settings,
    )

    assert result["cancel_at_period_end"] is True
    assert client._store["subscriptions"][0]["status"] == "active"
    assert client._store["subscriptions"][0]["tier"] == "node"


@pytest.mark.asyncio
async def test_cancel_soft_fails_missing_stripe_subscription(monkeypatch):
    org_id = "99999999-9999-9999-9999-999999999999"
    client = _FakeClient()
    client._store["org_billing"] = [
        {
            "org_id": org_id,
            "plan_code": "node",
            "billing_status": "trialing",
            "stripe_subscription_id": "sub_missing",
            "cancel_at_period_end": False,
        }
    ]

    settings = MagicMock()
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_service_role_key = "service-role"
    settings.stripe_secret_key = "sk_test_x"

    import stripe

    def _raise_missing(*_a, **_k):
        raise stripe.error.InvalidRequestError("No such subscription: sub_missing", param="id")

    monkeypatch.setattr(
        "app.services.stripe_service.cancel_subscription",
        _raise_missing,
    )
    monkeypatch.setattr(billing_router, "create_client", lambda *_a, **_k: client)
    monkeypatch.setattr(
        billing_router,
        "get_org_billing",
        lambda _c, oid: next(
            (r for r in client._store.get("org_billing", []) if r.get("org_id") == oid),
            None,
        ),
    )

    result = await billing_router.cancel_subscription(
        billing_router.CancelRequest(at_period_end=True),
        _admin=({"user_id": "u1"}, org_id),
        settings=settings,
    )

    assert result["cancel_at_period_end"] is True
    assert client._store["org_billing"][0]["cancel_at_period_end"] is True


@pytest.mark.asyncio
async def test_reactivate_clears_cancel_at_period_end(monkeypatch):
    org_id = "77777777-7777-7777-7777-777777777777"
    client = _FakeClient()
    client._store["org_billing"] = [
        {
            "org_id": org_id,
            "plan_code": "node",
            "billing_status": "active",
            "stripe_subscription_id": "sub_live",
            "cancel_at_period_end": True,
        }
    ]
    client._store["subscriptions"] = [
        {
            "org_id": org_id,
            "tier": "node",
            "status": "active",
            "stripe_subscription_id": "sub_live",
            "seat_count": 1,
            "lite_seats": 0,
        }
    ]

    settings = MagicMock()
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_service_role_key = "service-role"
    settings.stripe_secret_key = "sk_test_x"

    monkeypatch.setattr(
        "app.services.stripe_service.reactivate_subscription",
        lambda sub_id, settings: {"id": sub_id, "cancel_at_period_end": False},
    )
    monkeypatch.setattr(billing_router, "create_client", lambda *_a, **_k: client)
    monkeypatch.setattr(
        billing_router,
        "get_org_billing",
        lambda _c, oid: next(
            (r for r in client._store.get("org_billing", []) if r.get("org_id") == oid),
            None,
        ),
    )

    result = await billing_router.reactivate_subscription(
        _admin=({"user_id": "u1"}, org_id),
        settings=settings,
    )

    assert result["cancel_at_period_end"] is False
    assert client._store["org_billing"][0]["cancel_at_period_end"] is False
