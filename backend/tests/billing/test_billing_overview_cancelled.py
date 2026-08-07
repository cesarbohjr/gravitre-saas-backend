"""Billing overview must surface Canceled, not invent Trial/Active, after cancel."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.routers import billing as billing_router
from tests.billing.test_stripe_webhook_processing import _FakeClient


@pytest.mark.asyncio
async def test_overview_cancelled_org_without_subscription_row_shows_canceled(monkeypatch):
    org_id = "44444444-4444-4444-4444-444444444444"
    client = _FakeClient()
    client._store["org_billing"] = [
        {
            "org_id": org_id,
            "plan_code": "command",
            "billing_status": "cancelled",
            "stripe_subscription_id": None,
            "stripe_customer_id": "cus_x",
            "stripe_price_id": None,
        }
    ]
    client._store["subscriptions"] = []
    client._store["usage_records"] = []

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
    monkeypatch.setattr(
        billing_router,
        "get_plan_for_org",
        lambda _c, _oid: {"code": "node", "workflow_runs_included": 500, "ai_credits_included": 1000},
    )
    monkeypatch.setattr(
        billing_router,
        "_usage_from_records",
        lambda *_a, **_k: {
            "tier": "node",
            "period_start": "2026-08-01T00:00:00+00:00",
            "workflow_runs": 0,
            "ai_credits": 0,
        },
    )
    monkeypatch.setattr(
        billing_router,
        "_fetch_invoices_and_payment_methods",
        lambda **_k: ([], []),
    )
    monkeypatch.setattr(
        billing_router,
        "_weekly_workflow_totals",
        lambda *_a, **_k: [0, 0, 0, 0],
    )
    monkeypatch.setattr(
        billing_router,
        "_canonical_plan_code",
        lambda _c, _oid, _row: "node",
    )

    result = await billing_router.billing_overview(
        _user={"id": "u1"},
        org_id=org_id,
        settings=settings,
    )

    assert result["billing_status"] == "cancelled"
    assert result["subscription"]["status"] == "canceled"
    assert result["subscription"]["status"] != "trialing"
    assert result["subscription"]["status"] != "active"
    # Seeded canceled row — not an invented Trial.
    assert client._store["subscriptions"][0]["status"] == "canceled"
