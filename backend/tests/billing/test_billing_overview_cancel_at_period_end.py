"""Overview must surface org_billing.cancel_at_period_end (not subscriptions table)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.routers import billing as billing_router
from tests.billing.test_stripe_webhook_processing import _FakeClient


@pytest.mark.asyncio
async def test_overview_reads_cancel_at_period_end_from_org_billing(monkeypatch):
    org_id = "55555555-5555-5555-5555-555555555555"
    client = _FakeClient()
    client._store["org_billing"] = [
        {
            "org_id": org_id,
            "plan_code": "command",
            "billing_status": "active",
            "stripe_subscription_id": "sub_test",
            "stripe_customer_id": "cus_test",
            "stripe_price_id": "price_1TbcniGkcGZTLqrPGRwaFxgZ",
            "cancel_at_period_end": True,
            "current_period_end": "2026-09-14T00:00:00+00:00",
        }
    ]
    client._store["subscriptions"] = [
        {
            "org_id": org_id,
            "tier": "command",
            "status": "active",
            "stripe_subscription_id": "sub_test",
            "stripe_customer_id": "cus_test",
            "current_period_end": "2026-09-14T00:00:00+00:00",
        }
    ]
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
        lambda _c, _oid: {"code": "command", "workflow_runs_included": 10000, "ai_credits_included": 15000},
    )
    monkeypatch.setattr(
        billing_router,
        "_usage_from_records",
        lambda *_a, **_k: {
            "tier": "command",
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
        lambda _c, _oid, _row: "command",
    )

    result = await billing_router.billing_overview(
        _user={"id": "u1"},
        org_id=org_id,
        settings=settings,
    )

    assert result["subscription"]["cancel_at_period_end"] is True
    assert result["subscription"]["plan_unit_amount_cents"] == 29900
