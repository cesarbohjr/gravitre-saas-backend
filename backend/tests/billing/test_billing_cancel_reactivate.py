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
    assert sub_row["status"] == "trialing"


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
    assert client._store["subscriptions"][0]["status"] == "trialing"
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


def _lifecycle_client(monkeypatch, *, status="trialing", subscription_id="sub_trial", source="self"):
    client = _FakeClient()
    org_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    client._store["org_billing"] = [{
        "org_id": org_id, "plan_code": "node", "billing_status": status,
        "stripe_subscription_id": subscription_id, "billing_source": source,
        "cancel_at_period_end": True,
    }]
    client._store["subscriptions"] = [{
        "org_id": org_id, "tier": "node", "status": status,
        "stripe_subscription_id": subscription_id,
    }]
    settings = MagicMock(stripe_secret_key="sk_test_x")
    monkeypatch.setattr(billing_router, "shared_service_client", lambda *_a, **_k: client)
    return client, settings, org_id


@pytest.mark.asyncio
async def test_resume_trial_preserves_trial_in_both_billing_tables(monkeypatch):
    client, settings, org_id = _lifecycle_client(monkeypatch)
    monkeypatch.setattr("app.services.stripe_service.reactivate_subscription", lambda *_a, **_k: {
        "id": "sub_trial", "status": "trialing", "cancel_at_period_end": False,
    })
    result = await billing_router.reactivate_subscription(_admin=({"user_id": "u1"}, org_id), settings=settings)
    assert result["status"] == "trialing"
    assert client._store["org_billing"][0]["billing_status"] == "trialing"
    assert client._store["subscriptions"][0]["status"] == "trialing"


@pytest.mark.asyncio
async def test_resume_without_subscription_never_grants_paid_access(monkeypatch):
    from fastapi import HTTPException
    client, settings, org_id = _lifecycle_client(monkeypatch, status="cancelled", subscription_id=None)
    with pytest.raises(HTTPException) as error:
        await billing_router.reactivate_subscription(_admin=({"user_id": "u1"}, org_id), settings=settings)
    assert error.value.status_code == 409
    assert client._store["org_billing"][0]["billing_status"] == "cancelled"


@pytest.mark.asyncio
async def test_resume_missing_stripe_subscription_fails_closed(monkeypatch):
    import stripe
    from fastapi import HTTPException
    client, settings, org_id = _lifecycle_client(monkeypatch, status="cancelled")
    def missing(*_a, **_k):
        raise stripe.error.InvalidRequestError("No such subscription: sub_trial", param="id")
    monkeypatch.setattr("app.services.stripe_service.reactivate_subscription", missing)
    with pytest.raises(HTTPException):
        await billing_router.reactivate_subscription(_admin=({"user_id": "u1"}, org_id), settings=settings)
    assert client._store["org_billing"][0]["billing_status"] == "cancelled"
    assert client._store["org_billing"][0]["cancel_at_period_end"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["cancel", "reactivate"])
async def test_partner_billed_workspace_cannot_change_its_subscription(monkeypatch, operation):
    from fastapi import HTTPException
    client, settings, org_id = _lifecycle_client(monkeypatch, status="active", source="msp")
    with pytest.raises(HTTPException) as error:
        if operation == "cancel":
            await billing_router.cancel_subscription(billing_router.CancelRequest(at_period_end=False), _admin=({"user_id": "u1"}, org_id), settings=settings)
        else:
            await billing_router.reactivate_subscription(_admin=({"user_id": "u1"}, org_id), settings=settings)
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "BILLED_BY_PARTNER"
    assert client._store["org_billing"][0]["billing_status"] == "active"
