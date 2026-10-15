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
