"""Tests for one-shot + timezone cron helpers."""
from __future__ import annotations

from datetime import datetime, timezone

from app.workflows.cron import (
    ONCE_SENTINEL,
    compute_next_run_at,
    expand_cron_occurrences,
    is_once_schedule,
)


def test_is_once_schedule_by_type_and_sentinel():
    assert is_once_schedule(schedule_type="once") is True
    assert is_once_schedule(cron_expression=ONCE_SENTINEL) is True
    assert is_once_schedule(schedule_type="recurring", cron_expression="0 * * * *") is False


def test_compute_next_run_at_once_future():
    next_iso = compute_next_run_at(
        ONCE_SENTINEL,
        datetime(2026, 8, 1, tzinfo=timezone.utc),
        schedule_type="once",
        run_at="2026-08-15T15:00:00+00:00",
    )
    assert next_iso == "2026-08-15T15:00:00+00:00"


def test_compute_next_run_at_once_past_returns_none():
    next_iso = compute_next_run_at(
        ONCE_SENTINEL,
        datetime(2026, 8, 20, tzinfo=timezone.utc),
        schedule_type="once",
        run_at="2026-08-15T15:00:00+00:00",
    )
    assert next_iso is None


def test_expand_once_in_window():
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end = datetime(2026, 9, 1, tzinfo=timezone.utc)
    occ = expand_cron_occurrences(
        ONCE_SENTINEL,
        start,
        end,
        schedule_type="once",
        run_at="2026-08-15T15:00:00+00:00",
    )
    assert occ == ["2026-08-15T15:00:00+00:00"]


def test_daily_cron_respects_timezone():
    # Midnight America/Los_Angeles on 2026-08-01 is 07:00 UTC (PDT).
    next_iso = compute_next_run_at(
        "0 0 * * *",
        datetime(2026, 8, 1, tzinfo=timezone.utc),
        tz_name="America/Los_Angeles",
    )
    assert next_iso == "2026-08-01T07:00:00+00:00"


def test_ends_at_blocks_next():
    next_iso = compute_next_run_at(
        "0 * * * *",
        datetime(2026, 8, 1, 12, 1, tzinfo=timezone.utc),
        ends_at="2026-08-01T12:30:00+00:00",
    )
    # Next hourly fire would be 13:00 which is after ends_at.
    assert next_iso is None
