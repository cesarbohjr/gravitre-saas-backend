"""Tests for idempotent usage metering (billing correctness)."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock
import pytest

import app.billing.service as billing
from app.billing.service import (
    apply_usage_with_overage,
    derive_idempotency_key,
    record_assistant_model_usage_atomic,
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


def test_atomic_assistant_usage_does_not_fall_back_after_rpc_timeout():
    client = MagicMock()
    client.rpc.return_value.execute.side_effect = TimeoutError("commit result lost")
    with pytest.raises(TimeoutError):
        record_assistant_model_usage_atomic(client, "org-1", "call-1", 7, 100)
    client.table.assert_not_called()


def test_atomic_assistant_usage_replays_are_reported():
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = "duplicate"
    assert record_assistant_model_usage_atomic(client, "org-1", "call-1", 7, 100) == "duplicate"
    client.rpc.assert_called_once_with("record_assistant_model_usage", {
        "p_org_id": "org-1", "p_model_call_id": "call-1", "p_quantity": 7,
        "p_included": 100, "p_environment": "production",
    })


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


def test_failed_upsert_cannot_fall_back_to_non_idempotent_insert():
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.side_effect = TimeoutError("commit unknown")
    with pytest.raises(TimeoutError, match="commit unknown"):
        record_usage(client, "org-1", "production", "ai_credits", 3,
                     PERIOD_START, PERIOD_END,
                     metadata={"source": "assistant", "source_id": "mc-1"})
    client.table.return_value.insert.assert_not_called()


def test_usage_total_reads_all_pages_beyond_postgrest_row_limit():
    class Page:
        def __init__(self, entries):
            self.entries = entries
            self.start = 0
            self.end = 0

        def select(self, _columns): return self
        def eq(self, *_args): return self
        def order(self, _column): return self

        def range(self, start, end):
            self.start, self.end = start, end
            return self

        def execute(self):
            return MagicMock(data=self.entries[self.start:self.end + 1])

    entries = [{"id": str(i), "quantity": 2} for i in range(1201)]
    client = MagicMock()
    client.table.side_effect = lambda _name: Page(entries)
    assert billing._sum_usage(client, "org-1", "ai_credits", PERIOD_START, PERIOD_END) == 2402
