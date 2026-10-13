"""Behaviour-signal org discovery: distinct org ids, one small request per org, bounded."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.schedulers import entity_behavior_signals_scheduler as sched
from tests.services.fake_supabase_db import FakeSupabaseDB

NOW = datetime(2026, 10, 12, 12, tzinfo=UTC)
A, B, C = (
    "11111111-1111-4111-8111-111111111111",
    "22222222-2222-4222-8222-222222222222",
    "33333333-3333-4333-8333-333333333333",
)


class _CountingDB(FakeSupabaseDB):
    def __init__(self) -> None:
        super().__init__(range_filters=True)
        self.selects = 0

    def table(self, name: str):
        if name == "entity_observations":
            self.selects += 1
        return super().table(name)


def _obs(org: str, days_ago: float = 1) -> dict:
    return {"org_id": org, "observed_at": (NOW - timedelta(days=days_ago)).isoformat()}


def test_busy_org_does_not_hide_quieter_orgs() -> None:
    db = _CountingDB()
    # 25k rows for one org used to fill the old 20k-row scan before B or C was seen.
    db.tables["entity_observations"] = [_obs(B)] * 25_000 + [_obs(C), _obs(A)]
    assert sched.orgs_with_recent_observations(db, now=NOW) == [A, B, C]
    # One request per org found plus the one that finds no more.
    assert db.selects == 4


def test_old_observations_are_outside_the_window() -> None:
    db = _CountingDB()
    db.tables["entity_observations"] = [_obs(A, days_ago=sched.LOOKBACK_DAYS + 5), _obs(B)]
    assert sched.orgs_with_recent_observations(db, now=NOW) == [B]


def test_discovery_is_bounded() -> None:
    db = _CountingDB()
    db.tables["entity_observations"] = [_obs(A), _obs(B), _obs(C)]
    assert sched.orgs_with_recent_observations(db, now=NOW, max_orgs=2) == [A, B]
    assert db.selects == 2


def test_a_backend_ignoring_the_cursor_cannot_loop_forever() -> None:
    db = _CountingDB()
    db.range_filters = False  # gt/order ignored: every request returns the same first row
    db.tables["entity_observations"] = [_obs(A), _obs(B)]
    assert sched.orgs_with_recent_observations(db, now=NOW) == [A]
    assert db.selects == 2


def test_empty_table() -> None:
    db = _CountingDB()
    assert sched.orgs_with_recent_observations(db, now=NOW) == []
