"""Tests for Stripe webhook event processing edge cases."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.routers.webhooks import stripe as stripe_webhook_router


class _FakeTable:
    def __init__(self, store: dict[str, list[dict[str, Any]]], name: str):
        self._store = store
        self._name = name
        self._filters: dict[str, Any] = {}
        self._pending_insert: dict[str, Any] | None = None
        self._pending_upsert: dict[str, Any] | None = None
        self._pending_update: dict[str, Any] | None = None
        self._on_conflict: str | None = None

    def select(self, *_cols):
        return self

    def eq(self, key: str, value: Any):
        self._filters[key] = value
        return self

    def limit(self, _n: int):
        return self

    def insert(self, row: dict[str, Any]):
        self._pending_insert = row
        return self

    def upsert(self, row: dict[str, Any], on_conflict: str | None = None):
        self._pending_upsert = row
        self._on_conflict = on_conflict
        return self

    def update(self, row: dict[str, Any]):
        self._pending_update = row
        return self

    def execute(self):
        rows = self._store.setdefault(self._name, [])

        if self._pending_insert is not None:
            row = dict(self._pending_insert)
            rows.append(row)
            self._pending_insert = None
            return MagicMock(data=[row])

        if self._pending_upsert is not None:
            row = dict(self._pending_upsert)
            conflict_key = self._on_conflict or "org_id"
            conflict_value = row.get(conflict_key)
            existing = next((item for item in rows if item.get(conflict_key) == conflict_value), None)
            if existing:
                existing.update(row)
                stored = existing
            else:
                rows.append(row)
                stored = row
            self._pending_upsert = None
            self._on_conflict = None
            return MagicMock(data=[stored])

        if self._pending_update is not None:
            row = dict(self._pending_update)
            matches = [
                item
                for item in rows
                if all(item.get(k) == v for k, v in self._filters.items())
            ]
            for item in matches:
                item.update(row)
            self._pending_update = None
            self._filters = {}
            return MagicMock(data=matches)

        matches = [
            item
            for item in rows
            if all(item.get(k) == v for k, v in self._filters.items())
        ]
        self._filters = {}
        return MagicMock(data=matches)


class _FakeClient:
    def __init__(self):
        self._store: dict[str, list[dict[str, Any]]] = {}

    def table(self, name: str):
        return _FakeTable(self._store, name)


def _settings() -> MagicMock:
    settings = MagicMock()
    settings.stripe_price_id_node_monthly = "price_node_m"
    settings.stripe_price_id_node_annual = "price_node_a"
    settings.stripe_price_id_control_monthly = "price_control_m"
    settings.stripe_price_id_control_annual = "price_control_a"
    settings.stripe_price_id_command_monthly = "price_command_m"
    settings.stripe_price_id_command_annual = "price_command_a"
    settings.stripe_price_id_starter = "price_starter"
    settings.stripe_price_id_growth = "price_growth"
    settings.stripe_price_id_scale = "price_scale"
    return settings


def test_normalize_subscription_status_maps_incomplete_to_inactive():
    assert stripe_webhook_router._normalize_subscription_status("incomplete") == "inactive"
    assert stripe_webhook_router._normalize_subscription_status("unpaid") == "past_due"
    assert stripe_webhook_router._normalize_subscription_status("active") == "active"


def test_normalize_billing_plan_code_rejects_free():
    assert stripe_webhook_router._normalize_billing_plan_code("free") is None
    assert stripe_webhook_router._normalize_billing_plan_code("control") == "control"


def test_plan_from_subscription_items_skips_metered_and_reads_command():
    settings = _settings()
    settings.stripe_metered_price_id_command = "price_command_metered"
    data = {
        "items": {
            "data": [
                {
                    "price": {
                        "id": "price_command_metered",
                        "recurring": {"usage_type": "metered"},
                    },
                    "quantity": 1,
                },
                {
                    "price": {
                        "id": "price_command_m",
                        "recurring": {"usage_type": "licensed"},
                    },
                    "quantity": 1,
                },
            ]
        }
    }
    assert stripe_webhook_router._plan_from_subscription_items(settings, data) == "command"


def test_checkout_completed_writes_plan_code_from_metadata(monkeypatch):
    import sys
    import types

    client = _FakeClient()
    settings = _settings()
    org_id = "22222222-2222-2222-2222-222222222222"
    metadata = {"org_id": org_id, "plan_code": "command", "user_id": ""}
    data = {
        "id": "cs_test",
        "customer": "cus_cmd",
        "subscription": "sub_cmd",
        "metadata": metadata,
    }
    fake_entitlements = types.ModuleType("app.marketplace.entitlements")
    fake_entitlements.fulfill_entitlement_from_checkout = lambda *_a, **_k: None
    monkeypatch.setitem(sys.modules, "app.marketplace.entitlements", fake_entitlements)

    stripe_webhook_router._process_stripe_event(
        client,
        settings,
        "checkout.session.completed",
        data,
        metadata,
        org_id,
        {"id": "evt_checkout_cmd", "type": "checkout.session.completed"},
    )

    assert client._store["subscriptions"][0]["tier"] == "command"
    assert client._store["org_billing"][0]["plan_code"] == "command"


def test_process_subscription_updated_with_incomplete_status():
    client = _FakeClient()
    settings = _settings()
    org_id = "11111111-1111-1111-1111-111111111111"
    now = int(datetime.now(timezone.utc).timestamp())
    data = {
        "id": "sub_incomplete",
        "customer": "cus_123",
        "status": "incomplete",
        "current_period_start": now,
        "current_period_end": now + 86400,
        "metadata": {"org_id": org_id, "plan_code": "control"},
        "items": {"data": [{"price": {"id": "price_control_m"}, "quantity": 1}]},
    }

    stripe_webhook_router._process_stripe_event(
        client,
        settings,
        "customer.subscription.updated",
        data,
        data["metadata"],
        org_id,
        {"id": "evt_incomplete", "type": "customer.subscription.updated"},
    )

    subscriptions = client._store["subscriptions"]
    assert len(subscriptions) == 1
    assert subscriptions[0]["status"] == "inactive"
    assert subscriptions[0]["tier"] == "control"

    org_billing = client._store["org_billing"]
    assert len(org_billing) == 1
    assert org_billing[0]["billing_status"] == "pending"
    assert org_billing[0]["plan_code"] == "control"


def test_sanitize_org_id():
    assert stripe_webhook_router._sanitize_org_id(None) is None
    assert stripe_webhook_router._sanitize_org_id("") is None
    assert stripe_webhook_router._sanitize_org_id("  ") is None
    assert stripe_webhook_router._sanitize_org_id("org-1") == "org-1"


def test_check_webhook_idempotency_table_reachable():
    from app.billing.webhook_idempotency import check_webhook_idempotency_table

    client = _FakeClient()
    client._store["stripe_webhook_events"] = []
    result = check_webhook_idempotency_table(client)
    assert result["reachable"] is True
    assert result["error"] is None


def test_check_webhook_idempotency_table_missing():
    from app.billing.webhook_idempotency import check_webhook_idempotency_table

    class _MissingTableClient:
        def table(self, _name: str):
            raise Exception('Could not find the table "public.stripe_webhook_events" in the schema cache')

    result = check_webhook_idempotency_table(_MissingTableClient())
    assert result["reachable"] is False
    assert result["error"] == "table_missing"


@pytest.mark.asyncio
async def test_billing_webhook_health_endpoint(monkeypatch):
    from app.routers import billing as billing_router

    settings = MagicMock()
    settings.stripe_webhook_secret = "whsec_test"
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_service_role_key = "service-role"

    client = _FakeClient()
    client._store["stripe_webhook_events"] = []

    monkeypatch.setattr(billing_router, "create_client", lambda *_args, **_kwargs: client)

    result = await billing_router.billing_webhook_health(settings)
    assert result["status"] == "healthy"
    assert result["webhook_secret_set"] is True
    assert result["idempotency_table"]["reachable"] is True
