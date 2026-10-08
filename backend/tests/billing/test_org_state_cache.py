"""Per-org response caches for /api/billing/status, /api/entitlements, /api/auth/me.

Covers: cache hits for the shared production client, no caching for mock
clients, one read of org_billing / organizations per computed response, and
invalidation on webhook / billing / profile writes (incl. the billing gate).
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core import org_state_cache
from app.middleware import billing_gate
from app.middleware import entitlements as entitlements_mod
from app.routers import auth as auth_router
from app.routers import billing as billing_router
from app.routers.webhooks import stripe as stripe_webhook_router

ORG = "org-cache-1"
USER = "user-cache-1"


class _Resp:
    def __init__(self, data: list[dict[str, Any]]):
        self.data = data
        self.error = None
        self.count = len(data)


class _Query:
    def __init__(self, client: "_FakeClient", name: str):
        self._client = client
        self._name = name
        self._filters: list[tuple[str, str, Any]] = []
        self._op = "select"
        self._payload: Any = None
        self._on_conflict: str | None = None

    # read builders
    def select(self, *_a, **_k):
        return self

    def eq(self, key, value):
        self._filters.append(("eq", key, value))
        return self

    def in_(self, key, values):
        self._filters.append(("in", key, list(values)))
        return self

    def gte(self, *_a):
        return self

    def ilike(self, key, value):
        self._filters.append(("eq", key, value))
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a):
        return self

    # writes
    def insert(self, payload):
        self._op, self._payload = "insert", payload
        return self

    def upsert(self, payload, on_conflict=None, **_k):
        self._op, self._payload, self._on_conflict = "upsert", payload, on_conflict
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    def _matches(self, row: dict[str, Any]) -> bool:
        for kind, key, value in self._filters:
            if kind == "eq" and str(row.get(key)) != str(value):
                return False
            if kind == "in" and str(row.get(key)) not in {str(v) for v in value}:
                return False
        return True

    def execute(self):
        self._client.calls.append((self._name, self._op))
        rows = self._client.store.setdefault(self._name, [])
        if self._op == "insert":
            row = dict(self._payload)
            rows.append(row)
            return _Resp([row])
        if self._op == "upsert":
            row = dict(self._payload)
            key = (self._on_conflict or "org_id").split(",")[0]
            existing = next((r for r in rows if r.get(key) == row.get(key)), None)
            if existing is not None:
                existing.update(row)
                return _Resp([existing])
            rows.append(row)
            return _Resp([row])
        matches = [r for r in rows if self._matches(r)]
        if self._op == "update":
            for r in matches:
                r.update(self._payload)
            return _Resp(matches)
        if self._op == "delete":
            for r in matches:
                rows.remove(r)
            return _Resp(matches)
        return _Resp([dict(r) for r in matches])


class _FakeClient:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.store: dict[str, list[dict[str, Any]]] = {
            "org_billing": [
                {
                    "org_id": ORG,
                    "plan_code": "control",
                    "billing_status": "active",
                    "current_period_end": None,
                }
            ],
            "organizations": [
                {
                    "id": ORG,
                    "name": "Cache Co",
                    "settings": {"onboarding": {"seeded": True}},
                }
            ],
            "organization_members": [{"org_id": ORG, "user_id": USER, "role": "admin"}],
            "users": [{"id": "pub-1", "auth_user_id": USER, "org_id": ORG, "email": "u@example.com"}],
            "subscriptions": [{"org_id": ORG, "tier": "control", "status": "active", "seat_count": 2}],
        }

    def table(self, name: str):
        return _Query(self, name)

    def reads(self, table: str) -> int:
        return sum(1 for name, op in self.calls if name == table and op == "select")


@pytest.fixture
def fake_client(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(billing_router, "get_supabase_client", lambda _s: client)
    monkeypatch.setattr(entitlements_mod, "get_supabase_client", lambda _s: client)
    monkeypatch.setattr(auth_router, "shared_service_client", lambda *_a, **_k: client)
    monkeypatch.setattr(stripe_webhook_router, "shared_service_client", lambda *_a, **_k: client)
    return client


@pytest.fixture
def treat_fake_as_shared(monkeypatch, fake_client):
    """Pretend the fake is the process-wide production client so caching applies."""
    allowed = lambda c: c is fake_client  # noqa: E731
    monkeypatch.setattr(billing_router, "cache_allowed", allowed)
    monkeypatch.setattr(entitlements_mod, "cache_allowed", allowed)
    monkeypatch.setattr(auth_router, "cache_allowed", allowed)
    return fake_client


def _billing_status(settings):
    return billing_router.get_billing_status({"user_id": USER}, ORG, "production", settings)


def _me(settings, org_id=ORG):
    return auth_router.me({"user_id": USER, "email": "u@example.com"}, org_id, settings)


# --------------------------------------------------------------------------- reads


def test_billing_status_reads_each_org_row_once_per_compute(fake_client, mock_settings):
    payload = _billing_status(mock_settings)
    assert payload["planCode"] == "control"
    assert payload["billingState"] == "active"
    assert fake_client.reads("org_billing") == 1
    assert fake_client.reads("organizations") == 1
    assert fake_client.reads("org_billing_overrides") == 1


def test_entitlements_reads_org_billing_once(fake_client, mock_settings):
    result = entitlements_mod.resolve_entitlements(mock_settings, ORG)
    assert result["tier"] == "control"
    assert fake_client.reads("org_billing") == 1


def test_me_reuses_loaded_membership_and_org_rows(fake_client, mock_settings):
    payload = _me(mock_settings)
    assert payload["role"] == "admin"
    assert payload["onboarding"]["seeded"] is True
    assert payload["billing"]["plan_code"] == "control"
    assert payload["organizations"] == [{"id": ORG, "name": "Cache Co", "role": "admin"}]
    # memberships once (load_user_organizations), organizations once (with settings)
    assert fake_client.reads("organization_members") == 1
    assert fake_client.reads("organizations") == 1
    assert fake_client.reads("org_billing") == 1


# ------------------------------------------------------------------ hit / skip


def test_billing_status_is_cached_for_shared_client(treat_fake_as_shared, mock_settings):
    client = treat_fake_as_shared
    first = _billing_status(mock_settings)
    calls_after_first = len(client.calls)
    second = _billing_status(mock_settings)
    assert second == first
    assert len(client.calls) == calls_after_first  # served from cache
    # Callers get copies: mutating a response never leaks into the cache.
    second["plan"]["features"]["rbac"] = "mutated"
    second["usage"]["aiCredits"]["used"] = 999
    third = _billing_status(mock_settings)
    assert third == first


def test_billing_status_cache_is_keyed_by_environment(treat_fake_as_shared, mock_settings):
    client = treat_fake_as_shared
    _billing_status(mock_settings)
    n = len(client.calls)
    billing_router.get_billing_status({"user_id": USER}, ORG, "staging", mock_settings)
    assert len(client.calls) > n


def test_mock_clients_are_never_cached(fake_client, mock_settings):
    # No treat_fake_as_shared: the real is_shared_service_client check applies.
    _billing_status(mock_settings)
    n = len(fake_client.calls)
    _billing_status(mock_settings)
    assert len(fake_client.calls) > n
    entitlements_mod.resolve_entitlements(mock_settings, ORG)
    m = len(fake_client.calls)
    entitlements_mod.resolve_entitlements(mock_settings, ORG)
    assert len(fake_client.calls) > m
    _me(mock_settings)
    k = len(fake_client.calls)
    _me(mock_settings)
    assert len(fake_client.calls) > k
    assert len(org_state_cache.billing_status_cache) == 0
    assert len(org_state_cache.entitlements_cache) == 0
    assert len(org_state_cache.auth_me_cache) == 0


def test_cache_allowed_rejects_magicmock_clients():
    assert org_state_cache.cache_allowed(MagicMock()) is False
    assert org_state_cache.cache_allowed(object()) is False


def test_entitlements_and_me_cached_for_shared_client(treat_fake_as_shared, mock_settings):
    client = treat_fake_as_shared
    ent = entitlements_mod.resolve_entitlements(mock_settings, ORG)
    me_payload = _me(mock_settings)
    n = len(client.calls)
    assert entitlements_mod.resolve_entitlements(mock_settings, ORG) == ent
    assert _me(mock_settings) == me_payload
    assert len(client.calls) == n


# ---------------------------------------------------------------- invalidation


def test_stripe_webhook_write_invalidates_org_caches_and_billing_gate(treat_fake_as_shared, mock_settings):
    client = treat_fake_as_shared
    assert _billing_status(mock_settings)["billingState"] == "active"
    assert entitlements_mod.resolve_entitlements(mock_settings, ORG)["status"] == "active"
    assert _me(mock_settings)["billing"]["status"] == "active"
    billing_gate._remember_allowed((USER, ""), ORG)
    billing_gate._remember_allowed(("other-user", ORG), ORG)
    billing_gate._remember_allowed(("third-user", ""), "some-other-org")
    assert billing_gate._is_allowed_cached((USER, ""))

    stripe_webhook_router._process_stripe_event(
        client,
        mock_settings,
        "invoice.payment_failed",
        {"id": "in_1"},
        {"org_id": ORG},
        ORG,
        {"id": "evt_1", "type": "invoice.payment_failed"},
    )

    assert client.store["org_billing"][0]["billing_status"] == "past_due"
    status_payload = _billing_status(mock_settings)
    assert status_payload["billingState"] == "past_due"
    assert status_payload["canAccessApp"] is False
    assert entitlements_mod.resolve_entitlements(mock_settings, ORG)["status"] == "past_due"
    assert _me(mock_settings)["billing"]["status"] == "past_due"
    # Billing gate "allowed" decisions for that org are gone; others survive.
    assert not billing_gate._is_allowed_cached((USER, ""))
    assert not billing_gate._is_allowed_cached(("other-user", ORG))
    assert billing_gate._is_allowed_cached(("third-user", ""))


def test_billing_write_invalidates_even_when_processing_fails(treat_fake_as_shared, mock_settings, monkeypatch):
    client = treat_fake_as_shared
    _billing_status(mock_settings)
    assert len(org_state_cache.billing_status_cache) == 1

    def boom(*_a, **_k):
        raise RuntimeError("partial write")

    monkeypatch.setattr(stripe_webhook_router, "_apply_stripe_event", boom)
    with pytest.raises(RuntimeError):
        stripe_webhook_router._process_stripe_event(
            client, mock_settings, "invoice.payment_succeeded", {}, {"org_id": ORG}, ORG, {}
        )
    assert len(org_state_cache.billing_status_cache) == 0


def test_admin_plan_override_invalidates(treat_fake_as_shared, mock_settings, monkeypatch):
    from app.routers import billing_sync

    client = treat_fake_as_shared
    monkeypatch.setattr(billing_sync, "get_supabase_client", lambda _s: client)
    entitlements_mod.resolve_entitlements(mock_settings, ORG)
    _billing_status(mock_settings)
    billing_sync._set_hard_budget_override(mock_settings, ORG, True)
    assert len(org_state_cache.entitlements_cache) == 0
    assert len(org_state_cache.billing_status_cache) == 0


def test_profile_update_invalidates_me(treat_fake_as_shared, mock_settings):
    client = treat_fake_as_shared
    assert _me(mock_settings)["user"]["full_name"] is None
    body = auth_router.UserProfileUpdateRequest(full_name="New Name")
    auth_router.update_me(body, {"user_id": USER, "email": "u@example.com"}, mock_settings)
    assert client.store["users"][0]["full_name"] == "New Name"
    assert _me(mock_settings)["user"]["full_name"] == "New Name"


def test_membership_change_invalidates_me_for_other_orgs_members(treat_fake_as_shared, mock_settings):
    _me(mock_settings)
    assert len(org_state_cache.auth_me_cache) == 1
    org_state_cache.invalidate_org_state(ORG)
    assert len(org_state_cache.auth_me_cache) == 0
    _me(mock_settings)
    org_state_cache.invalidate_user_state(USER)
    assert len(org_state_cache.auth_me_cache) == 0


def test_compute_that_straddles_an_invalidation_is_not_cached(treat_fake_as_shared, mock_settings, monkeypatch):
    real_compute = billing_router._compute_billing_status

    def compute_then_write(*a, **k):
        payload = real_compute(*a, **k)
        org_state_cache.invalidate_org_state(ORG)  # concurrent write lands mid-request
        return payload

    monkeypatch.setattr(billing_router, "_compute_billing_status", compute_then_write)
    _billing_status(mock_settings)
    assert len(org_state_cache.billing_status_cache) == 0
