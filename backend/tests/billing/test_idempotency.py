"""Tests for idempotent usage metering (billing correctness)."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import app.billing.service as billing
from app.billing.service import (
    apply_usage_with_overage,
    derive_idempotency_key,
    record_usage,
)

PERIOD_START = date(2026, 5, 1)
PERIOD_END = date(2026, 5, 31)


class _FakeTable:
    """Simulates INSERT ... ON CONFLICT (org_id, idempotency_key) DO NOTHING."""

    def __init__(self, name: str, store: set[tuple]):
        self._name = name
        self._store = store
        self._payload: dict | None = None

    def upsert(self, payload, on_conflict=None, ignore_duplicates=False):  # noqa: ANN001
        self._payload = payload
        return self

    def insert(self, payload):  # noqa: ANN001
        self._payload = payload
        return self

    def execute(self):
        resp = MagicMock()
        key = (self._name, self._payload.get("org_id"), self._payload.get("idempotency_key"))
        if key in self._store:
            resp.data = []  # conflict -> skipped
        else:
            self._store.add(key)
            resp.data = [{"id": "row-id"}]
        return resp


class _FakeClient:
    def __init__(self):
        self.store: set[tuple] = set()

    def table(self, name: str) -> _FakeTable:
        return _FakeTable(name, self.store)


def test_derive_key_stable_with_source_id():
    meta = {"source": "model_call", "source_id": "mc-1"}
    k1 = derive_idempotency_key("org-1", "ai_credits", PERIOD_START, meta)
    k2 = derive_idempotency_key("org-1", "ai_credits", PERIOD_START, meta)
    assert k1 == k2
    assert k1 == "org-1:model_call:mc-1:2026-05-01"


def test_derive_key_unique_without_source_id():
    k1 = derive_idempotency_key("org-1", "ai_credits", PERIOD_START, {"source": "x"})
    k2 = derive_idempotency_key("org-1", "ai_credits", PERIOD_START, {"source": "x"})
    assert k1 != k2  # random anchor when no source_id


def test_record_usage_dedupes_on_repeat():
    client = _FakeClient()
    meta = {"source": "model_call", "source_id": "mc-1", "credits": 5}
    first = record_usage(client, "org-1", "production", "ai_credits", 5, PERIOD_START, PERIOD_END, metadata=meta)
    second = record_usage(client, "org-1", "production", "ai_credits", 5, PERIOD_START, PERIOD_END, metadata=meta)
    assert first is True
    assert second is False  # duplicate dropped


def test_record_usage_distinct_source_ids_both_insert():
    client = _FakeClient()
    a = record_usage(client, "org-1", "production", "ai_credits", 5, PERIOD_START, PERIOD_END,
                     metadata={"source": "model_call", "source_id": "mc-1"})
    b = record_usage(client, "org-1", "production", "ai_credits", 5, PERIOD_START, PERIOD_END,
                     metadata={"source": "model_call", "source_id": "mc-2"})
    assert a is True and b is True


def test_apply_usage_with_overage_is_idempotent(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(billing, "_sum_usage", lambda *a, **k: 0)
    plan = {"ai_credits_included": 1}  # tiny allowance -> overage path
    meta = {"source": "model_call", "source_id": "mc-9", "credits": 10}

    def _apply():
        apply_usage_with_overage(
            client=client, org_id="org-1", environment="production", metric_type="ai_credits",
            quantity=10, plan=plan, period_start=PERIOD_START, period_end=PERIOD_END, metadata=meta,
        )

    _apply()
    _apply()  # retry with identical source_id

    usage_rows = [k for k in client.store if k[0] == "usage_tracking"]
    overage_rows = [k for k in client.store if k[0] == "overage_usage"]
    assert len(usage_rows) == 1, "usage double-counted on retry"
    assert len(overage_rows) == 1, "overage double-counted on retry"
