from __future__ import annotations

from datetime import datetime, timezone

from app.workflows.cron import compute_next_run_at, expand_cron_occurrences


def test_compute_next_run_at_hourly_alias():
    base = datetime(2026, 5, 29, 10, 30, tzinfo=timezone.utc)
    nxt = compute_next_run_at("@hourly", base)
    assert nxt is not None
    assert "T11:00:00" in nxt


def test_compute_next_run_at_weekly_cron():
    base = datetime(2026, 5, 29, 10, 0, tzinfo=timezone.utc)
    nxt = compute_next_run_at("0 8 * * 1", base)
    assert nxt is not None
    parsed = datetime.fromisoformat(nxt)
    assert parsed > base
    assert parsed.hour == 8
    assert parsed.minute == 0


def test_compute_next_run_at_every_six_hours():
    base = datetime(2026, 5, 29, 10, 0, tzinfo=timezone.utc)
    nxt = compute_next_run_at("0 */6 * * *", base)
    assert nxt is not None
    parsed = datetime.fromisoformat(nxt)
    assert parsed.hour in {12, 18, 0, 6}


def test_expand_cron_occurrences_within_bounds():
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 4, tzinfo=timezone.utc)
    occurrences = expand_cron_occurrences("@daily", start, end)
    assert len(occurrences) == 3
