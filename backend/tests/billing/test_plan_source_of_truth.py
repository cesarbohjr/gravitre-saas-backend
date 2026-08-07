"""Regression: plan state must stay single-sourced (org_billing + Stripe price)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.billing.service import DEFAULT_PLANS
from app.middleware import entitlements as entitlements_mod
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
        self._order_desc = False

    def select(self, *_cols):
        return self

    def eq(self, key: str, value: Any):
        self._filters[key] = value
        return self

    def gte(self, key: str, value: Any):
        self._filters[f"gte:{key}"] = value
        return self

    def order(self, *_args, **_kwargs):
        self._order_desc = bool(_kwargs.get("desc"))
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
                item for item in rows if all(item.get(k) == v for k, v in self._filters.items() if not str(k).startswith("gte:"))
            ]
            for item in matches:
                item.update(row)
            self._pending_update = None
            self._filters = {}
            return MagicMock(data=matches)

        matches = [
            item for item in rows if all(item.get(k) == v for k, v in self._filters.items() if not str(k).startswith("gte:"))
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
    settings.supabase_url = "https://example.supabase.co"
    settings.supabase_service_role_key = "service"
    return settings


def test_subscription_updated_writes_stripe_price_id_and_command_plan():
    client = _FakeClient()
    # Stale Node price left behind after an upgrade (the live regression shape).
    client._store["org_billing"] = [
        {
            "org_id": "org-cmd",
            "plan_code": "node",
            "stripe_price_id": "price_node_m",
            "stripe_subscription_id": "sub_cmd",
        }
    ]
    settings = _settings()
    now = int(datetime.now(timezone.utc).timestamp())
    data = {
        "id": "sub_cmd",
        "customer": "cus_cmd",
        "status": "active",
        "current_period_start": now,
        "current_period_end": now + 86400,
        "metadata": {"org_id": "org-cmd", "plan_code": "node"},  # stale metadata
        "items": {
            "data": [
                {
                    "price": {
                        "id": "price_command_m",
                        "recurring": {"usage_type": "licensed"},
                    },
                    "quantity": 1,
                },
                {
                    "price": {
                        "id": "price_command_metered",
                        "recurring": {"usage_type": "metered"},
                    }
                },
            ]
        },
    }

    stripe_webhook_router._process_stripe_event(
        client,
        settings,
        "customer.subscription.updated",
        data,
        data["metadata"],
        "org-cmd",
        {"id": "evt_upgrade", "type": "customer.subscription.updated"},
    )

    billing = client._store["org_billing"][0]
    assert billing["plan_code"] == "command"
    assert billing["stripe_price_id"] == "price_command_m"
    assert client._store["subscriptions"][0]["tier"] == "command"


def test_resolve_plan_code_prefers_items_over_stale_metadata():
    settings = _settings()
    data = {
        "metadata": {"plan_code": "node"},
        "items": {
            "data": [
                {"price": {"id": "price_command_m", "recurring": {"usage_type": "licensed"}}},
            ]
        },
    }
    assert stripe_webhook_router._resolve_plan_code(settings, data, data["metadata"]) == "command"


def test_resolve_entitlements_uses_org_billing_not_stale_subscription_tier(monkeypatch):
    settings = _settings()
    client = _FakeClient()
    org_id = "org-ent"
    client._store["org_billing"] = [
        {"org_id": org_id, "plan_code": "command", "billing_status": "active"}
    ]
    client._store["subscriptions"] = [
        {"org_id": org_id, "tier": "node", "status": "active", "seat_count": 1, "lite_seats": 0}
    ]
    client._store["usage_records"] = []
    client._store["billing_plans"] = [
        {
            "code": "command",
            "name": "Command",
            "workflow_runs_included": 10000,
            "ai_credits_included": 15000,
            "workflows_limit": 120,
            "agents_limit": 8,
            "features": {"approvals": True, "advanced_connectors": True},
        }
    ]

    monkeypatch.setattr(entitlements_mod, "get_supabase_client", lambda _s: client)
    # get_plan_for_org / get_org_billing hit real service helpers — patch them for isolation.
    monkeypatch.setattr(
        entitlements_mod,
        "get_plan_for_org",
        lambda _c, _o: {
            "code": "command",
            "workflow_runs_included": 10000,
            "ai_credits_included": 15000,
            "workflows_limit": 120,
            "agents_limit": 8,
            "features": {"approvals": True, "advanced_connectors": True},
        },
    )
    monkeypatch.setattr(
        entitlements_mod,
        "get_org_billing",
        lambda _c, _o: {"plan_code": "command", "billing_status": "active"},
    )

    result = entitlements_mod.resolve_entitlements(settings, org_id)
    assert result["tier"] == "command"
    assert result["limits"]["runs_per_month"] == 10000
    assert result["limits"]["ai_credits_included"] == 15000


@pytest.mark.parametrize(
    "code,runs,ai",
    [
        ("node", 500, 1000),
        ("control", 2500, 5000),
        ("command", 10000, 15000),
    ],
)
def test_default_plans_matrix_matches_public_entitlements(code: str, runs: int, ai: int):
    plan = DEFAULT_PLANS[code]
    assert int(plan["workflow_runs_included"]) == runs
    assert int(plan["ai_credits_included"]) == ai
    assert entitlements_mod.TIER_LIMITS[code]["runs_per_month"] == runs
