"""Recovery accepts only a bounded recent window and replays through the RPC."""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest


path = Path(__file__).resolve().parents[1] / "reconcile_assistant_billing.py"
spec = importlib.util.spec_from_file_location("reconcile_assistant_billing", path)
assert spec and spec.loader
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


def _window():
    now = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
    before = now - timedelta(minutes=15)
    return before - timedelta(minutes=30), before


class _Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


def test_recovery_is_read_only_by_default(monkeypatch):
    monkeypatch.setattr(recovery, "datetime", _Clock)
    since, before = _window()
    row = {"id": "call-1", "org_id": "org-1", "model_name": "test",
           "input_tokens": 100, "output_tokens": 10}
    client = MagicMock()
    client.table.return_value.select.return_value.like.return_value.gte.return_value.lt.return_value.order.return_value.range.return_value.execute.return_value.data = [row]
    monkeypatch.setattr(recovery, "record_assistant_model_usage_atomic", lambda *a: pytest.fail("write"))
    summary = recovery.reconcile(client, since, before, apply=False)
    assert summary["candidates"] == 1 and summary["inserted"] == 0
    assert summary["dry_run"] is True


def test_apply_replays_duplicates_and_uses_persisted_tokens(monkeypatch):
    monkeypatch.setattr(recovery, "datetime", _Clock)
    since, before = _window()
    row = {"id": "call-1", "org_id": "org-1", "model_name": "test",
           "input_tokens": 100, "output_tokens": 10}
    client = MagicMock()
    client.table.return_value.select.return_value.like.return_value.gte.return_value.lt.return_value.order.return_value.range.return_value.execute.return_value.data = [row]
    monkeypatch.setattr(recovery, "get_plan_for_org", lambda *_: {"ai_credits_included": 500})
    calls = []
    def record(*args):
        calls.append(args)
        return "duplicate"
    monkeypatch.setattr(recovery, "record_assistant_model_usage_atomic", record)
    summary = recovery.reconcile(client, since, before, apply=True)
    assert summary["duplicate"] == 1 and summary["errors"] == 0
    assert calls[0][1:3] == ("org-1", "call-1")
    assert calls[0][3] == recovery.compute_ai_credits(100, 10, "test")


def test_recovery_rejects_historical_month(monkeypatch):
    monkeypatch.setattr(recovery, "datetime", _Clock)
    _, before = _window()
    client = MagicMock()
    with pytest.raises(ValueError, match="current UTC billing month"):
        recovery.reconcile(client, before - timedelta(days=40), before, apply=True)
    client.table.assert_not_called()


def _ledger_client(calls, usage):
    client = MagicMock()
    model = MagicMock()
    model.select.return_value = model
    model.like.return_value = model
    model.gte.return_value = model
    model.lt.return_value = model
    model.order.return_value = model
    model.range.return_value = model
    model.execute.return_value.data = calls
    ledger = MagicMock()
    ledger.select.return_value = ledger
    ledger.eq.return_value = ledger
    ledger.in_.return_value = ledger
    ledger.range.return_value = ledger
    ledger.execute.return_value.data = usage
    client.table.side_effect = lambda table: model if table == "model_calls" else ledger
    return client


def test_recovery_counts_only_missing_calls(monkeypatch):
    monkeypatch.setattr(recovery, "datetime", _Clock)
    since, before = _window()
    call = {"id": "call-1", "org_id": "org-1", "model_name": "test",
            "input_tokens": 100, "output_tokens": 10}
    key = "org-1:assistant:call-1:2026-10-01"
    usage = {"id": "usage-1", "org_id": "org-1", "idempotency_key": key,
             "source": "assistant", "source_id": "call-1", "model_name": "test",
             "input_tokens": 100, "output_tokens": 10, "quantity": 1}
    summary = recovery.reconcile(_ledger_client([call], [usage]), since, before, apply=False)
    assert summary["scanned"] == 1
    assert summary["already_billed"] == 1
    assert summary["candidates"] == 0


def test_recovery_preflight_refuses_mismatched_existing_usage(monkeypatch):
    monkeypatch.setattr(recovery, "datetime", _Clock)
    since, before = _window()
    call = {"id": "call-1", "org_id": "org-1", "model_name": "test",
            "input_tokens": 100, "output_tokens": 10}
    usage = {"idempotency_key": "org-1:assistant:call-1:2026-10-01",
             "source": "assistant", "source_id": "call-1", "model_name": "test",
             "input_tokens": 100, "output_tokens": 10, "quantity": 9}
    client = _ledger_client([call], [usage])
    monkeypatch.setattr(recovery, "record_assistant_model_usage_atomic", lambda *a: pytest.fail("write"))
    with pytest.raises(ValueError, match="preflight"):
        recovery.reconcile(client, since, before, apply=True)


def test_recovery_preflight_refuses_truncated_window(monkeypatch):
    monkeypatch.setattr(recovery, "datetime", _Clock)
    since, before = _window()
    calls = [{"id": f"call-{i}", "org_id": "org-1", "model_name": "test",
              "input_tokens": 100, "output_tokens": 10} for i in range(2)]
    client = _ledger_client(calls, [])
    monkeypatch.setattr(recovery, "record_assistant_model_usage_atomic", lambda *a: pytest.fail("write"))
    with pytest.raises(ValueError, match="preflight"):
        recovery.reconcile(client, since, before, apply=True, max_calls=1)


def test_zero_token_charge_is_reported_as_mismatch(monkeypatch):
    monkeypatch.setattr(recovery, "datetime", _Clock)
    since, before = _window()
    calls = [{"id": "call-1", "org_id": "org-1", "input_tokens": 0, "output_tokens": 0}]
    usage = [{"idempotency_key": "org-1:assistant:call-1:2026-10-01", "quantity": 1}]
    summary = recovery.reconcile(_ledger_client(calls, usage), since, before, apply=False)
    assert summary["zero_tokens"] == 1
    assert summary["mismatched"] == 1 and summary["errors"] == 1
