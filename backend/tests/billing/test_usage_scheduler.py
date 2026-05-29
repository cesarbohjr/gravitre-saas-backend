"""Tests for the in-process usage-sync scheduler."""
from __future__ import annotations

from unittest.mock import MagicMock

import app.billing.usage_scheduler as scheduler
from app.billing.usage_scheduler import (
    _run_once,
    start_usage_sync_scheduler,
    stop_usage_sync_scheduler,
)


async def test_run_once_invokes_reporter(mock_settings, monkeypatch):
    called = {}

    def fake_report(ps, pe, settings):
        called["ps"] = ps
        called["pe"] = pe
        return {"orgs": 2, "reported_rows": 5}

    monkeypatch.setattr(scheduler, "report_usage_for_active_orgs", fake_report)
    await _run_once(mock_settings)
    assert "ps" in called and "pe" in called


async def test_run_once_swallows_errors(mock_settings, monkeypatch):
    def boom(ps, pe, settings):
        raise RuntimeError("db down")

    monkeypatch.setattr(scheduler, "report_usage_for_active_orgs", boom)
    # Must not raise — a failed tick should never kill the loop.
    await _run_once(mock_settings)


async def test_start_disabled_when_interval_zero(mock_settings, monkeypatch):
    settings = mock_settings.model_copy(update={"usage_sync_interval_seconds": 0})
    monkeypatch.setattr(scheduler, "get_settings", lambda: settings)
    task = start_usage_sync_scheduler()
    assert task is None


async def test_start_returns_task_when_enabled(mock_settings, monkeypatch):
    settings = mock_settings.model_copy(update={"usage_sync_interval_seconds": 3600})
    monkeypatch.setattr(scheduler, "get_settings", lambda: settings)
    # Avoid any real work if the loop ticked.
    monkeypatch.setattr(scheduler, "report_usage_for_active_orgs", lambda *a, **k: {"orgs": 0, "reported_rows": 0})
    task = start_usage_sync_scheduler()
    assert task is not None
    await stop_usage_sync_scheduler(task)  # clean cancel
    assert task.cancelled() or task.done()


async def test_stop_handles_none():
    await stop_usage_sync_scheduler(None)  # no-op, must not raise
