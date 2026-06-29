"""Tests for Stripe webhook event idempotency."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.billing.webhook_idempotency import (
    claim_webhook_event,
    is_webhook_event_processed,
    release_webhook_event_claim,
)


class FakeClient:
    def __init__(self):
        self._store: dict[str, dict] = {}

    def table(self, name: str):
        return _FakeTable(self._store)


class _FakeTable:
    def __init__(self, store: dict[str, dict]):
        self._store = store
        self._filters: dict[str, str] = {}
        self._pending_insert: dict | None = None
        self._delete = False

    def select(self, *_cols):
        return self

    def eq(self, key: str, value: str):
        self._filters[key] = value
        return self

    def limit(self, _n: int):
        return self

    def insert(self, row: dict):
        self._pending_insert = row
        return self

    def delete(self):
        self._delete = True
        return self

    def execute(self):
        if self._pending_insert is not None:
            row = self._pending_insert
            key = row["stripe_event_id"]
            if key in self._store:
                raise Exception('duplicate key value violates unique constraint "23505"')
            self._store[key] = row
            self._pending_insert = None
            return MagicMock(data=[row])

        if self._delete:
            key = self._filters.get("stripe_event_id")
            removed = self._store.pop(key, None) if key else None
            self._delete = False
            self._filters = {}
            return MagicMock(data=[removed] if removed else [])

        matches = [
            row
            for row in self._store.values()
            if all(row.get(k) == v for k, v in self._filters.items())
        ]
        self._filters = {}
        return MagicMock(data=matches[:1])


def test_duplicate_webhook_event_skipped():
    client = FakeClient()
    assert claim_webhook_event(client, "evt_1", "customer.subscription.updated", "org-1") is True
    assert is_webhook_event_processed(client, "evt_1") is True
    assert claim_webhook_event(client, "evt_1", "customer.subscription.updated", "org-1") is False


def test_first_occurrence_processes_normally():
    client = FakeClient()
    assert is_webhook_event_processed(client, "evt_new") is False
    assert claim_webhook_event(client, "evt_new", "invoice.payment_succeeded", "org-2") is True


def test_failed_processing_does_not_record_as_processed():
    client = FakeClient()
    assert claim_webhook_event(client, "evt_fail", "checkout.session.completed", "org-3") is True
    release_webhook_event_claim(client, "evt_fail")
    assert is_webhook_event_processed(client, "evt_fail") is False
    assert claim_webhook_event(client, "evt_fail", "checkout.session.completed", "org-3") is True


def test_concurrent_duplicate_webhooks_only_process_once():
    client = FakeClient()
    first = claim_webhook_event(client, "evt_race", "customer.subscription.updated", "org-4")
    second = claim_webhook_event(client, "evt_race", "customer.subscription.updated", "org-4")
    assert first is True
    assert second is False


@pytest.mark.asyncio
async def test_stripe_webhook_handler_skips_duplicate(monkeypatch):
    from app.routers.webhooks import stripe as stripe_webhook_router

    client = FakeClient()
    claim_webhook_event(client, "evt_dup", "customer.subscription.updated", "org-5")

    settings = MagicMock()
    settings.stripe_webhook_secret = "whsec_test"
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_service_role_key = "service-role"

    event = MagicMock()
    event.id = "evt_dup"
    event.type = "customer.subscription.updated"
    event.get = lambda key, default=None: {
        "id": "evt_dup",
        "type": "customer.subscription.updated",
        "data": {"object": {"metadata": {"org_id": "org-5"}}},
    }.get(key, default)

    request = MagicMock()
    async def _body():
        return b"{}"
    request.body = _body
    request.headers = {"stripe-signature": "sig"}

    monkeypatch.setattr(stripe_webhook_router, "verify_webhook", lambda *_args, **_kwargs: event)
    monkeypatch.setattr(stripe_webhook_router, "create_client", lambda *_args, **_kwargs: client)

    result = await stripe_webhook_router.stripe_webhook(request, settings)
    assert result["status"] == "already_processed"
