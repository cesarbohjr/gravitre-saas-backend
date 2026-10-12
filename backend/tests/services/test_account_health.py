"""Phase 7: explainable account health and the daily behaviour-signal pass."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tests.services.fake_supabase_db import FakeSupabaseDB

ORG = "11111111-1111-4111-8111-111111111111"
NOW = datetime(2026, 10, 12, 12, tzinfo=UTC)
ENTITY = {"id": "e1", "display_name": "Acme"}


def _obs(dim: str, label: str, score: float, days_ago: float, n: int, quote: str = "q") -> dict:
    return {
        "dimension": dim,
        "label": label,
        "score": score,
        "evidence_quote": quote,
        "source_system": "zendesk",
        "source_record_id": f"t{n}",
        "observed_at": (NOW - timedelta(days=days_ago)).isoformat(),
        "status": "active",
    }


def _falling_sentiment() -> list[dict]:
    scores = [1.0, 1.0, 1.0, -1.0, -1.0, -1.0]
    return [
        _obs("sentiment", "positive" if s > 0 else "negative", s, 25 - i * 4, i, quote=f"msg {i}")
        for i, s in enumerate(scores)
    ]


def _by_key(health: dict) -> dict:
    return {d["key"]: d for d in health["dimensions"]}


def test_thin_evidence_is_unknown_never_a_guess():
    from app.services.account_health import build_account_health

    h = build_account_health(ENTITY, [_obs("sentiment", "negative", -1.0, 1, 1)], [], [], now=NOW)
    dims = _by_key(h)
    assert dims["sentiment"]["status"] == "unknown"
    assert dims["sentiment"]["coverage"]["observations"] == 1
    assert dims["contact_volume"]["status"] == "unknown"
    assert dims["contact_gap"]["status"] == "unknown"
    assert dims["open_work"]["status"] == "unknown"
    assert h["compositeScore"] is None


def test_every_dimension_carries_definition_and_kind():
    from app.services.account_health import DEFINITIONS, build_account_health

    h = build_account_health(ENTITY, [], [], [], now=NOW)
    assert {d["key"] for d in h["dimensions"]} == set(DEFINITIONS)
    for d in h["dimensions"]:
        assert d["definition"] and d["kind"] in {"leading", "lagging"}


def test_falling_sentiment_is_at_risk_with_quoted_evidence():
    from app.services.account_health import build_account_health

    dims = _by_key(build_account_health(ENTITY, _falling_sentiment(), [], [], now=NOW))
    s = dims["sentiment"]
    assert s["status"] == "at_risk"
    assert s["value"]["direction"] == "falling"
    assert s["evidence"] and s["evidence"][0].startswith('"msg 5"')
    assert len(s["evidence"]) <= 3


def test_retracted_observations_do_not_count():
    from app.services.account_health import build_account_health

    rows = _falling_sentiment()
    for r in rows:
        r["status"] = "retracted"
    assert _by_key(build_account_health(ENTITY, rows, [], [], now=NOW))["sentiment"]["status"] == "unknown"


def test_behaviour_signal_thresholds():
    from app.services.account_health import build_account_health

    def signals(volume: float, gap: float) -> list[dict]:
        day = NOW.date().isoformat()
        return [
            {"signal": "contact_volume_change", "value": volume, "baseline": 2, "window_end": day, "evidence_count": 9},
            {"signal": "contact_gap_days", "value": gap, "window_end": day, "evidence_count": 5},
        ]

    calm = _by_key(build_account_health(ENTITY, [], signals(1.0, 3), [], now=NOW))
    assert calm["contact_volume"]["status"] == "healthy" and calm["contact_gap"]["status"] == "healthy"
    busy = _by_key(build_account_health(ENTITY, [], signals(2.5, 35), [], now=NOW))
    assert busy["contact_volume"]["status"] == "watch" and busy["contact_gap"]["status"] == "watch"
    quiet = _by_key(build_account_health(ENTITY, [], signals(0.0, 61), [], now=NOW))
    assert quiet["contact_gap"]["status"] == "at_risk"


def test_latest_signal_wins():
    from app.services.account_health import build_account_health

    old = {"signal": "contact_gap_days", "value": 90, "window_end": "2026-10-01", "evidence_count": 4}
    new = {"signal": "contact_gap_days", "value": 2, "window_end": "2026-10-12", "evidence_count": 4}
    dims = _by_key(build_account_health(ENTITY, [], [old, new], [], now=NOW))
    assert dims["contact_gap"]["value"] == 2


def test_linked_work_ignores_proposed_and_flags_blocked():
    from app.services.account_health import build_account_health

    work = [
        {"title": "Renewal call", "status": "in_progress"},
        {"title": "Fix SSO", "status": "blocked"},
        {"title": "Idea", "status": "proposed"},
    ]
    w = _by_key(build_account_health(ENTITY, [], [], work, now=NOW))["open_work"]
    assert w["status"] == "watch"
    assert w["coverage"]["linked"] == 2
    assert w["evidence"] == ["Fix SSO is blocked"]


def test_list_ranks_at_risk_accounts_first():
    from app.services.account_health import list_account_health

    db = FakeSupabaseDB()
    db.tables["entity_observations"] = [
        {**r, "org_id": ORG, "entity_id": "e2"} for r in _falling_sentiment()
    ] + [{**_obs("sentiment", "positive", 1.0, 2, 1), "org_id": ORG, "entity_id": "e1"}]
    db.tables["entity_behavior_signals"] = []
    db.tables["org_business_entities"] = [
        {"id": "e1", "display_name": "Acme", "org_id": ORG},
        {"id": "e2", "display_name": "Zeta", "org_id": ORG},
    ]
    db.tables["work_objects"] = []
    out = list_account_health(db, ORG, now=NOW)
    names = [a["entity"]["name"] for a in out["accounts"]]
    assert names == ["Zeta", "Acme"]
    assert out["accounts"][0]["atRisk"] == ["Customer sentiment"]


def test_routes_are_404_when_off():
    from app.routers.entity_observations import (
        get_account_health,
        list_account_health_route,
    )

    off = SimpleNamespace(account_health_enabled=False)
    with pytest.raises(HTTPException) as e:
        list_account_health_route({}, ORG, off)
    assert e.value.status_code == 404
    with pytest.raises(HTTPException) as e:
        get_account_health("e1", {}, ORG, off)
    assert e.value.status_code == 404


def test_behaviour_signal_pass_runs_once_per_recent_org():
    from app.schedulers.entity_behavior_signals_scheduler import run_behavior_signals

    db = FakeSupabaseDB()
    db.tables["entity_observations"] = [
        {"org_id": ORG, "observed_at": NOW.isoformat()},
        {"org_id": ORG, "observed_at": NOW.isoformat()},
        {"org_id": "o2", "observed_at": NOW.isoformat()},
    ]
    written = run_behavior_signals(db, now=NOW)
    calls = [w for w in db.writes if w[0] == "rpc"]
    assert sorted(c[2]["p_org_id"] for c in calls) == sorted([ORG, "o2"])
    assert all(c[1] == "compute_entity_behavior_signals" for c in calls)
    assert written == {ORG: 0, "o2": 0}


def test_behaviour_scheduler_is_off_by_default():
    from app.config import Settings

    s = Settings()
    assert s.entity_behavior_signals_enabled is False
    assert s.account_health_enabled is False
