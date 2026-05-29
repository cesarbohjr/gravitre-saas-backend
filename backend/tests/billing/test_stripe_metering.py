"""Tests for Stripe usage metering (report_usage_to_stripe) and sync endpoints."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
import stripe

import app.billing.stripe_metering as metering
from app.billing.stripe_metering import report_usage_to_stripe
from app.config import Settings, get_settings
from app.main import app

PERIOD_START = date(2026, 5, 1)
PERIOD_END = date(2026, 5, 31)


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
        stripe_secret_key="sk_test_123",
        stripe_meter_event_name="ai_credits_used",
    )
    base.update(overrides)
    return Settings(**base)


class _FakeResp:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self._is_update = False
        self._payload = None
        self._in_ids = None

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def in_(self, _col, ids):
        self._in_ids = ids
        return self

    def update(self, payload):
        self._is_update = True
        self._payload = payload
        return self

    def execute(self):
        if self._is_update:
            self.client.updates.append((self.table, self._payload, self._in_ids))
            return _FakeResp([])
        return _FakeResp(list(self.client.data.get(self.table, [])))


class _FakeClient:
    def __init__(self, data):
        self.data = data
        self.updates: list = []

    def table(self, name):
        return _FakeQuery(self, name)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _fake_client_with_usage():
    return _FakeClient(
        {
            "usage_tracking": [
                {"id": "u1", "quantity": 5, "credits": 5},
                {"id": "u2", "quantity": 7, "credits": 7},
            ],
            "subscriptions": [{"stripe_customer_id": "cus_123"}],
        }
    )


def test_report_usage_reports_and_marks_rows(monkeypatch):
    create = MagicMock()
    monkeypatch.setattr(stripe.billing.MeterEvent, "create", create)
    client = _fake_client_with_usage()

    res = report_usage_to_stripe("org-1", PERIOD_START, PERIOD_END, _settings(), client=client, dry_run=False)

    assert res["reported"] is True
    assert res["reported_rows"] == 2
    assert res["credits"] == 12
    create.assert_called_once()
    _, kwargs = create.call_args
    assert kwargs["event_name"] == "ai_credits_used"
    assert kwargs["payload"] == {"stripe_customer_id": "cus_123", "value": "12"}
    assert "identifier" in kwargs and "timestamp" in kwargs
    # rows marked reported
    assert client.updates and client.updates[0][0] == "usage_tracking"
    assert client.updates[0][2] == ["u1", "u2"]


def test_dry_run_does_not_call_stripe(monkeypatch):
    create = MagicMock()
    monkeypatch.setattr(stripe.billing.MeterEvent, "create", create)
    client = _fake_client_with_usage()

    res = report_usage_to_stripe("org-1", PERIOD_START, PERIOD_END, _settings(), client=client, dry_run=True)

    assert res["dry_run"] is True
    assert res["reported"] is False
    assert res["credits"] == 12
    assert res["unreported_rows"] == 2
    create.assert_not_called()
    assert client.updates == []


def test_no_unreported_rows_is_noop(monkeypatch):
    create = MagicMock()
    monkeypatch.setattr(stripe.billing.MeterEvent, "create", create)
    client = _FakeClient({"usage_tracking": [], "subscriptions": [{"stripe_customer_id": "cus_123"}]})

    res = report_usage_to_stripe("org-1", PERIOD_START, PERIOD_END, _settings(), client=client)

    assert res["reported_rows"] == 0
    assert res["credits"] == 0
    create.assert_not_called()


def test_no_customer_skips(monkeypatch):
    create = MagicMock()
    monkeypatch.setattr(stripe.billing.MeterEvent, "create", create)
    client = _FakeClient(
        {"usage_tracking": [{"id": "u1", "quantity": 5, "credits": 5}], "subscriptions": [], "org_billing": []}
    )

    res = report_usage_to_stripe("org-1", PERIOD_START, PERIOD_END, _settings(), client=client)

    assert res["error"] == "no_customer"
    assert res["reported_rows"] == 0
    create.assert_not_called()


async def test_internal_sync_requires_secret_configured(async_client):
    # Default test env has no INTERNAL_API_SECRET -> 503.
    resp = await async_client.post("/api/internal/billing/sync-usage")
    assert resp.status_code == 503


async def test_internal_sync_rejects_bad_secret(async_client):
    app.dependency_overrides[get_settings] = lambda: _settings(internal_api_secret="right-secret")
    resp = await async_client.post(
        "/api/internal/billing/sync-usage",
        headers={"X-Internal-Secret": "wrong-secret"},
    )
    assert resp.status_code == 401


async def test_internal_sync_accepts_valid_secret(async_client, monkeypatch):
    app.dependency_overrides[get_settings] = lambda: _settings(internal_api_secret="right-secret")
    monkeypatch.setattr(
        metering,
        "report_usage_for_active_orgs",
        lambda *a, **k: {"orgs": 0, "reported_rows": 0, "results": []},
    )
    # Patch the symbol imported into the router module too.
    import app.routers.billing_sync as billing_sync

    monkeypatch.setattr(
        billing_sync,
        "report_usage_for_active_orgs",
        lambda *a, **k: {"orgs": 0, "reported_rows": 0, "results": []},
    )
    resp = await async_client.post(
        "/api/internal/billing/sync-usage",
        headers={"X-Internal-Secret": "right-secret"},
    )
    assert resp.status_code == 200
    assert resp.json()["orgs"] == 0
