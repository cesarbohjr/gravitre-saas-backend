"""One account reading: account health, the feed and the churn advisory agree."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import account_health as ah
from app.services import recommendation_feed as rf
from app.services.ingestion_interlock import LIFECYCLE_PREREQUISITES
from tests.services.fake_supabase_db import FakeSupabaseDB

ORG = "11111111-1111-4111-8111-111111111111"
NOW = datetime(2026, 10, 12, 12, tzinfo=UTC)


def _obs(dim: str, scores: list[float], *, label: str = "negative", eid: str = "e1", quote: str = "q") -> list[dict[str, Any]]:
    return [
        {
            "entity_id": eid,
            "dimension": dim,
            "label": label,
            "score": s,
            "evidence_quote": f"{quote} {i}",
            "source_system": "zendesk",
            "source_record_id": f"{dim}-{i}",
            "observed_at": (NOW - timedelta(days=25 - i * 4)).isoformat(),
            "status": "active",
        }
        for i, s in enumerate(scores)
    ]


FALLING = [1.0, 1.0, 1.0, -1.0, -1.0, -1.0]
RISING = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
STEADY_LOW = [0.0] * 6


def _health(rows: list[dict[str, Any]], signals: list[dict[str, Any]] | None = None, eid: str = "e1", name: str = "Acme"):
    return ah.build_account_health({"id": eid, "display_name": name}, rows, signals or [], [], now=NOW)


def _churn(customer_id: str, level: str, score: float) -> dict[str, Any]:
    return {
        "id": f"churn-advisory-{customer_id}",
        "kind": "churn_risk_advisory",
        "title": f"Account {customer_id}: {level} churn risk",
        "reason": "Review with a human.",
        "evidence": {"customerId": customer_id, "riskScore": score, "riskLevel": level, "contributingFactors": ["low usage"]},
    }


# --------------------------------------------------------------------------- one reading


def test_read_observations_is_the_rule_health_feed_and_card_share():
    rows = _obs("sentiment", FALLING) + _obs("expansion_interest", RISING, label="explicit") + _obs("urgency", [0.0] * 3)
    by = {r["key"]: r for r in ah.read_observations(rows, now=NOW)}
    assert by["sentiment"]["status"] == "at_risk" and by["sentiment"]["notable"]
    assert by["expansion_interest"]["status"] == "healthy" and by["expansion_interest"]["opportunity"]
    assert by["urgency"]["status"] == "unknown" and not by["urgency"]["notable"]
    health = {d["key"]: d for d in _health(rows)["dimensions"]}
    for key, r in by.items():
        assert health[key]["status"] == r["status"]
    # The feed surfaces exactly the notable dimensions of that reading.
    feed = rf.items_from_accounts({"e1": "Acme"}, rows, [], now=NOW)
    assert {i["dimension"] for i in feed} == {k for k, r in by.items() if r["notable"]}


def test_feed_quotes_follow_account_health_and_skip_neutral_labels():
    rows = _obs("sentiment", FALLING)
    rows[-1]["label"] = "neutral"
    rows[-1]["evidence_quote"] = "just checking in"
    item = rf.items_from_accounts({"e1": "Acme"}, rows, [], now=NOW)[0]
    assert all("just checking in" not in e for e in item["evidence"])
    assert item["evidence"][0].startswith('"q 4" (zendesk, ')


def test_feed_uses_the_latest_behaviour_signal_like_account_health():
    signals = [
        {"entity_id": "e1", "signal": "contact_volume_change", "value": 3.0, "window_end": "2026-10-10"},
        {"entity_id": "e1", "signal": "contact_volume_change", "value": 1.0, "window_end": "2026-10-11"},
        {"entity_id": "e1", "signal": "contact_gap_days", "value": 45, "window_end": "2026-10-11"},
    ]
    items = rf.items_from_accounts({"e1": "Acme"}, [], signals, now=NOW)
    assert [i["title"] for i in items] == ["Acme: no customer message for 45 days"]


# --------------------------------------------------------------------------- unified items


def test_one_item_per_account_with_each_source_labelled():
    rows = _obs("sentiment", FALLING) + _obs("support_friction", RISING, label="severe")
    signals = [{"signal": "contact_volume_change", "value": 3.0, "baseline": 2, "window_end": "2026-10-11", "evidence_count": 9}]
    items = rf.items_from_account_health([_health(rows, signals)], [_churn("e1", "high", 0.82)])
    assert len(items) == 1
    item = items[0]
    assert item["id"] == "account:e1" and item["kind"] == "account_health" and item["advisoryOnly"]
    assert item["sources"] == ["account_health", "churn_model"] and item["source"] == "account_health+churn_model"
    assert any(e.startswith("[account health] Customer sentiment: at risk") for e in item["evidence"])
    assert any(e.startswith("[churn model] high churn risk") for e in item["evidence"])
    assert "high churn risk (model)" in item["title"]
    assert item["disagreement"] is False


def test_churn_model_and_customer_language_disagreeing_shows_both():
    # Model says high risk; customers' churn-risk language is steady and low.
    rows = _obs("churn_risk_language", STEADY_LOW, label="hint")
    item = rf.items_from_account_health([_health(rows)], [_churn("e1", "high", 0.9)])[0]
    assert item["disagreement"] is True
    sources = {r["source"]: r for r in item["readings"]}
    assert sources["churn_model"]["reading"] == "high" and "score 0.90" in sources["churn_model"]["basis"]
    assert "untrained" in sources["churn_model"]["basis"]
    assert sources["entity_observations"]["reading"] == "healthy"
    assert "6 observations" in sources["entity_observations"]["basis"]
    assert "neither overrides the other" in item["why"]

    # And the other way: model low, customers talking about leaving.
    rows = _obs("churn_risk_language", RISING, label="explicit")
    item = rf.items_from_account_health([_health(rows)], [_churn("e1", "low", 0.1)])[0]
    assert item["disagreement"] is True
    assert {r["source"]: r["reading"] for r in item["readings"]} == {"churn_model": "low", "entity_observations": "at_risk"}


def test_no_disagreement_claimed_without_enough_customer_evidence():
    assert rf.churn_disagreement("high", "unknown") is False
    assert rf.churn_disagreement("high", None) is False
    assert rf.churn_disagreement("medium", "healthy") is False
    item = rf.items_from_account_health([_health(_obs("churn_risk_language", [0.0] * 2))], [_churn("e1", "high", 0.9)])[0]
    assert item["disagreement"] is False
    assert {r["source"]: r["reading"] for r in item["readings"]}["entity_observations"] == "unknown"


def test_churn_cards_match_bound_records_and_unmatched_stand_alone():
    items = rf.items_from_account_health(
        [],
        [
            _churn("hs-123", "high", 0.8),
            _churn("cust-9", "medium", 0.5),
            _churn("cust-low", "low", 0.1),
            {"kind": "churn_risk_pending", "evidence": {"customerId": "cust-p"}},
        ],
        entity_for_customer={"hs-123": "e2"},
        names={"e2": "Globex"},
    )
    by_id = {i["id"]: i for i in items}
    assert set(by_id) == {"account:e2", "churn:cust-9"}
    assert by_id["account:e2"]["title"].startswith("Globex: high churn risk")
    assert by_id["churn:cust-9"]["source"] == "churn_model"
    assert "could not be compared" in by_id["churn:cust-9"]["why"]


def test_quiet_accounts_and_low_churn_with_calm_health_are_left_out():
    calm = _health(_obs("sentiment", [0.5] * 6, label="positive"))
    assert rf.items_from_account_health([calm], [_churn("e1", "low", 0.1)]) == []


# --------------------------------------------------------------------------- build_feed wiring


class _DB(FakeSupabaseDB):
    pass


def _feed(settings: Any, db: FakeSupabaseDB, churn: AsyncMock) -> dict[str, Any]:
    engine = MagicMock()
    engine.collect_signals = AsyncMock(return_value={"signals": []})
    with patch("app.services.business_signals_engine.get_business_signals_engine", return_value=engine), patch(
        "app.services.recommendation_heuristics_service.load_heuristic_signals",
        return_value={"connected_connectors": [], "usage_by_connector": {}, "installed_packs": [], "lookback_days": 30},
    ), patch("app.services.churn_advisory_service.build_churn_advisory_cards", churn):
        return asyncio.run(rf.build_feed(db, settings, org_id=ORG, user_id=None))


def _seeded_db() -> FakeSupabaseDB:
    db = _DB()
    now = datetime.now(UTC)
    rows = []
    for i, s in enumerate(FALLING):
        rows.append(
            {
                "org_id": ORG,
                "entity_id": "e1",
                "dimension": "sentiment",
                "label": "negative" if s < 0 else "positive",
                "score": s,
                "evidence_quote": f"msg {i}",
                "source_system": "zendesk",
                "source_record_id": f"t{i}",
                "observed_at": (now - timedelta(days=25 - i * 4)).isoformat(),
                "status": "active",
            }
        )
    db.tables["entity_observations"] = rows
    db.tables["org_business_entities"] = [{"org_id": ORG, "id": "e1", "display_name": "Acme"}]
    return db


@pytest.mark.usefixtures("lifecycle_runtime_ready")
def test_flag_off_keeps_todays_feed_and_never_reads_churn():
    churn = AsyncMock(return_value={"recommendations": [_churn("e1", "high", 0.9)], "trained": True})
    settings = SimpleNamespace(entity_observations_enabled=True, **dict(LIFECYCLE_PREREQUISITES))
    out = _feed(settings, _seeded_db(), churn)
    churn.assert_not_awaited()
    assert "churn_advisory" not in out["sources"]
    assert [i["id"] for i in out["items"]] == ["account:e1:sentiment"]


def test_flag_on_merges_health_and_churn_without_logging_predictions():
    churn = AsyncMock(return_value={"recommendations": [_churn("e1", "high", 0.9)], "trained": True})
    settings = SimpleNamespace(entity_observations_enabled=True, account_feed_unified_v1=True)
    out = _feed(settings, _seeded_db(), churn)
    assert churn.await_args.kwargs["log_predictions"] is False
    assert out["sources"]["accounts"] == "ok" and out["sources"]["churn_advisory"] == "ok"
    accounts = [i for i in out["items"] if i.get("businessEntityId") == "e1"]
    assert len(accounts) == 1 and accounts[0]["sources"] == ["account_health", "churn_model"]
    assert any("trained on this organisation's outcomes" in e for e in accounts[0]["evidence"])


def test_churn_advisory_can_be_read_without_logging_predictions():
    from app.services import churn_advisory_service as cas

    scorer = MagicMock(_model=object(), registry_ref={"model_id": "m", "version": 1})
    scorer.predict_structured = AsyncMock(return_value={"risk_score": 0.8, "risk_level": "high"})
    row = {"customer_id": "c1", "features": {"days_since_last_activity": 40.0}}

    def run(log: bool) -> MagicMock:
        logged = MagicMock()
        with patch.object(cas, "training_gate_status", return_value={"current": 9, "required": 5}), patch.object(
            cas, "list_churn_training_rows", return_value=[]
        ), patch.object(cas, "list_unlabeled_churn_signal_rows", return_value=[row]), patch.object(
            cas, "_log_checkable_prediction", logged
        ), patch("app.ml.model_catalog.load_org_trained_catalog_model", AsyncMock(return_value=scorer)):
            payload = asyncio.run(
                cas.build_churn_advisory_cards(ORG, settings=MagicMock(), client=MagicMock(), log_predictions=log)
            )
        assert payload["trained"] is True and payload["recommendations"][0]["kind"] == "churn_risk_advisory"
        return logged

    assert run(True).call_count == 1
    assert run(False).call_count == 0


def test_flag_on_survives_a_failing_churn_advisory():
    churn = AsyncMock(side_effect=RuntimeError("model store down"))
    settings = SimpleNamespace(entity_observations_enabled=True, account_feed_unified_v1=True)
    out = _feed(settings, _seeded_db(), churn)
    assert out["sources"]["churn_advisory"] == "error" and out["sources"]["accounts"] == "ok"
    assert [i["id"] for i in out["items"] if i.get("businessEntityId") == "e1"] == ["account:e1"]
