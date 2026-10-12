"""CHURN_ENTITY_FEATURES_ENABLED: mapping, missing data, leakage, promotion refusal.

All data here is synthetic. Nothing in these tests says the entity features
improve churn prediction on real customers; they check the plumbing and gates.
"""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.config import Settings
from app.ml import intelligence_training as it
from app.ml.base import ModelMetrics
from app.ml.churn_entity_features import (
    AMBIGUOUS,
    ENTITY_FEATURE_KEYS,
    LABEL_GAP_DAYS,
    MAPPED,
    UNMAPPED,
    entity_features_as_of,
    join_features,
    load_entity_features,
    map_churn_customers_to_entities,
    training_as_of,
)
from app.ml.churn_scoring import FEATURE_KEYS, ChurnRiskScorer
from app.ml.churn_time_split_eval import (
    REFUSE_INSUFFICIENT,
    REFUSE_MARGIN,
    REFUSE_NO_COMPARISON,
    REFUSE_PRECISION,
    baseline_gate_refusal,
    evaluate_entity_challenger,
    precision_at_k,
)

ORG = "org-1"
NOW = datetime(2026, 10, 1, tzinfo=UTC)


# --------------------------------------------------------------------------- fake db
class _Query:
    def __init__(self, db: _FakeDB, table: str) -> None:
        self.db, self.table, self.filters = db, table, []

    def select(self, *_a: Any) -> _Query:
        return self

    def eq(self, col: str, val: Any) -> _Query:
        self.filters.append(lambda r: str(r.get(col)) == str(val))
        return self

    def in_(self, col: str, vals: list[Any]) -> _Query:
        allowed = {str(v) for v in vals}
        self.filters.append(lambda r: str(r.get(col)) in allowed)
        return self

    def gte(self, col: str, val: Any) -> _Query:
        self.filters.append(lambda r: str(r.get(col)) >= str(val))
        return self

    def lt(self, col: str, val: Any) -> _Query:
        self.filters.append(lambda r: str(r.get(col)) < str(val))
        return self

    def limit(self, *_a: Any) -> _Query:
        return self

    def execute(self) -> Any:
        if self.table in self.db.fail:
            raise RuntimeError("boom")
        self.db.queries.append(self.table)
        rows = [r for r in self.db.tables.get(self.table, []) if all(f(r) for f in self.filters)]
        return SimpleNamespace(data=rows)


class _FakeDB:
    def __init__(self, **tables: list[dict[str, Any]]) -> None:
        self.tables = tables
        self.fail: set[str] = set()
        self.queries: list[str] = []

    def table(self, name: str) -> _Query:
        return _Query(self, name)


def _binding(rid: str, eid: str, *, org: str = ORG, system: str = "hubspot") -> dict[str, Any]:
    return {"org_id": org, "entity_id": eid, "system": system, "resource_type": "company", "resource_id": rid}


def _obs(eid: str, dim: str, score: float, when: datetime, msg: str, **extra: Any) -> dict[str, Any]:
    return {
        "org_id": ORG,
        "entity_id": eid,
        "dimension": dim,
        "score": score,
        "source_system": "hubspot",
        "source_record_id": msg,
        "observed_at": when.isoformat(),
        "status": "active",
        "correction": None,
        "corrected_at": None,
        **extra,
    }


def _messages(eid: str, dim: str, scores: list[float], end: datetime, step_days: int = 3) -> list[dict[str, Any]]:
    return [
        _obs(eid, dim, s, end - timedelta(days=step_days * (len(scores) - i)), f"{eid}-{dim}-{i}")
        for i, s in enumerate(scores)
    ]


# --------------------------------------------------------------------------- mapping
def test_mapping_uses_bindings_and_never_guesses():
    db = _FakeDB(
        org_business_entity_bindings=[
            _binding("cust-a", "ent-1"),
            _binding("cust-a", "ent-1", system="zendesk"),  # same entity twice: still mapped
            _binding("cust-b", "ent-2"),
            _binding("cust-b", "ent-3", system="zendesk"),  # two entities: ambiguous
            _binding("cust-c", "ent-9", org="other-org"),  # another tenant: ignored
        ],
        org_business_entities=[{"org_id": ORG, "id": "ent-4", "display_name": "cust-d"}],
    )
    out = map_churn_customers_to_entities(db, ORG, ["cust-a", "cust-b", "cust-c", "cust-d"])
    assert out["cust-a"] == {"status": MAPPED, "entity_id": "ent-1"}
    assert out["cust-b"]["status"] == AMBIGUOUS and out["cust-b"]["entity_id"] is None
    assert out["cust-c"] == {"status": UNMAPPED, "entity_id": None}
    # An entity whose *name* equals the customer id is not a binding: unmapped.
    assert out["cust-d"] == {"status": UNMAPPED, "entity_id": None}
    assert db.queries == ["org_business_entity_bindings"]


def test_mapping_failure_leaves_everything_unmapped():
    db = _FakeDB(org_business_entity_bindings=[_binding("cust-a", "ent-1")])
    db.fail.add("org_business_entity_bindings")
    out = map_churn_customers_to_entities(db, ORG, ["cust-a"])
    assert out == {"cust-a": {"status": UNMAPPED, "entity_id": None}}


# --------------------------------------------------------------------------- missing data
def test_insufficient_evidence_is_missing_not_zero():
    as_of = NOW
    # 3 sentiment observations from 3 messages: below the 5-observation trend floor.
    rows = _messages("e", "sentiment", [-1.0, -1.0, -1.0], as_of)
    feats = entity_features_as_of(rows, [], as_of=as_of)
    assert feats["obs_message_count"] == 3.0
    assert feats["obs_sentiment_count"] == 3.0
    assert feats["obs_sentiment_mean"] is None and feats["obs_sentiment_delta"] is None
    # Coverage exists, so a dimension with no observations is a real count of 0 ...
    assert feats["obs_churn_risk_language_count"] == 0.0
    # ... but its mean is still missing, never 0.
    assert feats["obs_churn_risk_language_mean"] is None
    assert feats["sig_contact_gap_days"] is None


def test_no_coverage_means_every_entity_feature_missing():
    feats = entity_features_as_of([], [], as_of=NOW)
    assert set(feats) == set(ENTITY_FEATURE_KEYS)
    assert all(v is None for v in feats.values())


def test_enough_evidence_gives_counts_means_and_signals():
    rows = _messages("e", "sentiment", [1.0, 1.0, 0.0, -1.0, -1.0, -1.0], NOW)
    sig = [
        {"signal": "contact_gap_days", "value": 12, "window_end": (NOW - timedelta(days=5)).date().isoformat()},
        {"signal": "contact_gap_days", "value": 40, "window_end": (NOW - timedelta(days=2)).date().isoformat()},
        {"signal": "contact_volume_change", "value": 3, "window_end": (NOW - timedelta(days=40)).date().isoformat()},
    ]
    feats = entity_features_as_of(rows, sig, as_of=NOW)
    assert feats["obs_sentiment_count"] == 6.0
    assert feats["obs_sentiment_mean"] == pytest.approx(-1 / 6, abs=1e-3)
    assert feats["obs_sentiment_delta"] is not None and feats["obs_sentiment_delta"] < 0
    assert feats["sig_contact_gap_days"] == 40.0  # latest closed window
    assert feats["sig_contact_volume_change"] is None  # too old: missing


def test_scorer_keeps_missing_entity_features_as_nan_and_crm_as_zero():
    scorer = ChurnRiskScorer(feature_names=list(FEATURE_KEYS) + ["obs_sentiment_mean"])
    vec = scorer._vectorize([{"open_support_tickets": 2}])
    assert vec[0][list(FEATURE_KEYS).index("days_since_last_activity")] == 0.0
    assert math.isnan(vec[0][-1])
    # Baseline scorer is untouched: only the five CRM keys.
    assert ChurnRiskScorer().feature_names == list(FEATURE_KEYS)
    assert ChurnRiskScorer().has_optional_features() is False


@pytest.mark.asyncio
async def test_entity_model_trains_and_predicts_with_missing_values():
    rng = np.random.default_rng(1)
    keys = list(FEATURE_KEYS) + ["obs_sentiment_mean"]
    rows, labels = [], []
    for i in range(60):
        churned = i % 2
        row = {k: float(rng.integers(1, 5)) for k in FEATURE_KEYS}
        row["obs_sentiment_mean"] = None if i % 3 == 0 else (-0.8 if churned else 0.6)
        rows.append(row)
        labels.append(churned)
    scorer = ChurnRiskScorer(feature_names=keys)
    metrics = await scorer.train(rows, labels)
    assert metrics.training_samples and metrics.validation_samples
    out = await scorer.predict_structured(customer_features={"open_support_tickets": 1})
    assert out["status"] == "ok" and 0.0 <= out["risk_score"] <= 1.0
    clone = ChurnRiskScorer()
    clone.load(scorer.save())
    assert clone.has_optional_features() is True


# --------------------------------------------------------------------------- leakage
def test_no_future_observations_corrections_or_signals():
    as_of = NOW
    past = _messages("e", "churn_risk_language", [0.0, 0.0, 0.0, 0.0, 0.0], as_of)
    future = [
        _obs("e", "churn_risk_language", 1.0, as_of, "at-as-of"),  # exactly at as_of: excluded
        _obs("e", "churn_risk_language", 1.0, as_of + timedelta(days=3), "after"),
    ]
    # A correction made after as_of must not rewrite what was knowable then.
    late_fix = dict(past[0], status="corrected", correction={"score": 1.0},
                    corrected_at=(as_of + timedelta(days=1)).isoformat())
    early_fix = dict(past[1], status="corrected", correction={"score": 0.5},
                     corrected_at=(as_of - timedelta(days=1)).isoformat())
    rows = [late_fix, early_fix, *past[2:], *future]
    feats = entity_features_as_of(rows, [
        {"signal": "contact_gap_days", "value": 99, "window_end": as_of.date().isoformat()},
        {"signal": "contact_gap_days", "value": 7, "window_end": (as_of - timedelta(days=1)).date().isoformat()},
    ], as_of=as_of)
    assert feats["obs_churn_risk_language_count"] == 5.0
    assert feats["obs_churn_risk_language_mean"] == pytest.approx(0.1)  # only the early fix counts
    assert feats["sig_contact_gap_days"] == 7.0


def test_training_rows_are_cut_label_gap_before_the_label():
    label_at = NOW
    as_of = training_as_of(label_at.isoformat())
    assert as_of == label_at - timedelta(days=LABEL_GAP_DAYS)
    # "We are cancelling" said a week before the label is after as_of: not a feature.
    rows = _messages("ent-1", "churn_risk_language", [0.0] * 5, as_of) + [
        _obs("ent-1", "churn_risk_language", 1.0, label_at - timedelta(days=7), "cancel-mail")
    ]
    db = _FakeDB(
        org_business_entity_bindings=[_binding("cust-a", "ent-1")],
        entity_observations=[{**r, "org_id": ORG} for r in rows],
        entity_behavior_signals=[],
    )
    feats, coverage = load_entity_features(db, ORG, [("cust-a", as_of), ("cust-x", as_of)])
    assert coverage[MAPPED] == 1 and coverage[UNMAPPED] == 1
    assert feats[0]["obs_churn_risk_language_count"] == 5.0
    assert feats[0]["obs_churn_risk_language_mean"] == 0.0
    assert all(v is None for v in feats[1].values())
    joined = join_features({"open_support_tickets": 2.0}, feats[0])
    assert joined["open_support_tickets"] == 2.0 and "obs_sentiment_mean" in joined


def test_load_entity_features_read_failure_is_missing():
    db = _FakeDB(org_business_entity_bindings=[_binding("cust-a", "ent-1")], entity_observations=[])
    db.fail.add("entity_observations")
    feats, coverage = load_entity_features(db, ORG, [("cust-a", NOW)])
    assert coverage["read_failed"] is True
    assert all(v is None for v in feats[0].values())


# --------------------------------------------------------------------------- harness + gate
def _synthetic(n: int, *, entity_signal: bool, seed: int = 7) -> tuple[list[dict], list[int], list[str]]:
    """Synthetic only. CRM features are weak; the entity feature carries the label when asked."""
    rng = np.random.default_rng(seed)
    rows, labels, times = [], [], []
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(n):
        churned = int(rng.random() < 0.4)
        row: dict[str, Any] = {k: float(rng.integers(1, 6)) for k in FEATURE_KEYS}
        row["days_since_last_activity"] += 1.5 * churned * float(rng.random() < 0.3)
        for k in ENTITY_FEATURE_KEYS:
            row[k] = None
        if entity_signal:
            row["obs_churn_risk_language_mean"] = (0.8 if churned else 0.1) + float(rng.normal(0, 0.1))
        else:
            row["obs_churn_risk_language_mean"] = float(rng.random())
        rows.append(row)
        labels.append(churned)
        times.append((start + timedelta(days=i)).isoformat())
    return rows, labels, times


def test_precision_at_k():
    assert precision_at_k([1, 0, 1, 0], [0.9, 0.8, 0.7, 0.1], 2) == 0.5
    assert precision_at_k([], [], 2) is None


def test_harness_reports_both_models_on_the_same_split_and_passes_when_better():
    rows, labels, times = _synthetic(200, entity_signal=True)
    report, challenger, metrics = evaluate_entity_challenger(rows, labels, times, entity_keys=ENTITY_FEATURE_KEYS)
    assert challenger is not None and metrics is not None
    assert report["train_samples"] + report["holdout_samples"] == 200
    assert report["holdout_from"] == times[report["train_samples"]]  # later window held out
    assert report["challenger"]["auc_roc"] > report["baseline"]["auc_roc"] + 0.02
    assert report["passes_baseline_gate"] is True
    assert metrics.custom_metrics["bg_compared"] is True
    assert it.champion_challenger_decision(metrics, None, has_champion=False)[0] is True


def test_harness_refuses_when_not_better_by_margin():
    rows, labels, times = _synthetic(200, entity_signal=False)
    report, _challenger, metrics = evaluate_entity_challenger(rows, labels, times, entity_keys=ENTITY_FEATURE_KEYS)
    assert report["passes_baseline_gate"] is False
    assert report["reason"] in {REFUSE_MARGIN, REFUSE_PRECISION}
    deploy, reason, ev = it.champion_challenger_decision(metrics, None, has_champion=False)
    assert deploy is False and reason == report["reason"]
    assert "bg_baseline_auc_roc" in ev["baseline_gate"]


def test_harness_refuses_below_minimum_labelled_even_if_better():
    rows, labels, times = _synthetic(50, entity_signal=True)
    report, challenger, metrics = evaluate_entity_challenger(rows, labels, times, entity_keys=ENTITY_FEATURE_KEYS)
    assert challenger is not None
    assert report["reason"] == REFUSE_INSUFFICIENT
    assert it.champion_challenger_decision(metrics, {"auc_roc": 0.1}, has_champion=True)[:2] == (
        False,
        REFUSE_INSUFFICIENT,
    )


def test_harness_without_time_split_does_not_produce_a_challenger():
    rows, labels, _times = _synthetic(80, entity_signal=True)
    report, challenger, metrics = evaluate_entity_challenger(rows, labels, ["bad"] * 80, entity_keys=ENTITY_FEATURE_KEYS)
    assert (challenger, metrics) == (None, None)
    assert report["reason"] == "time_split_unavailable"


def test_gate_rechecks_numbers_and_floors_cannot_be_lowered():
    good = {
        "bg_compared": True,
        "bg_labelled_samples": 100,
        "bg_min_labelled_samples": 60,
        "bg_auc_margin": 0.02,
        "bg_baseline_auc_roc": 0.70,
        "bg_challenger_auc_roc": 0.75,
        "bg_baseline_precision_at_k": 0.5,
        "bg_challenger_precision_at_k": 0.6,
    }
    assert baseline_gate_refusal(good) is None
    assert baseline_gate_refusal({**good, "bg_challenger_auc_roc": 0.71}) == REFUSE_MARGIN
    assert baseline_gate_refusal({**good, "bg_challenger_precision_at_k": 0.4}) == REFUSE_PRECISION
    assert baseline_gate_refusal({**good, "bg_challenger_auc_roc": None}) == REFUSE_NO_COMPARISON
    # Stored thresholds can raise the bar but never lower it below the code floor.
    assert baseline_gate_refusal({**good, "bg_labelled_samples": 40, "bg_min_labelled_samples": 10}) == REFUSE_INSUFFICIENT
    assert baseline_gate_refusal({**good, "bg_auc_margin": 0.0, "bg_challenger_auc_roc": 0.705}) == REFUSE_MARGIN
    # Metrics without a baseline comparison are not affected (every other trainer).
    assert baseline_gate_refusal({"split": "time"}) is None
    deploy, reason, _ = it.champion_challenger_decision(
        ModelMetrics(auc_roc=0.99, custom_metrics={**good, "bg_challenger_auc_roc": 0.70}),
        {"auc_roc": 0.5},
        has_champion=True,
    )
    assert (deploy, reason) == (False, REFUSE_MARGIN)


# --------------------------------------------------------------------------- trainer wiring
def _labelled(rows: list[dict], labels: list[int], times: list[str]) -> list[dict]:
    return [
        {"customer_id": f"cust-{i}", "features": {k: r[k] for k in FEATURE_KEYS}, "churned": bool(y),
         "measured_at": t}
        for i, (r, y, t) in enumerate(zip(rows, labels, times, strict=True))
    ]


def _registry() -> MagicMock:
    registry = MagicMock()
    registry.list_models = AsyncMock(return_value=[])
    registry.create_model = AsyncMock(return_value=SimpleNamespace(id="m-churn"))
    registry.add_version = AsyncMock(side_effect=[SimpleNamespace(version=1), SimpleNamespace(version=2)])
    registry.deploy_version = AsyncMock(return_value=True)
    registry.get_version_metrics = AsyncMock(return_value=None)
    return registry


@pytest.mark.asyncio
async def test_flag_off_trainer_never_reads_entity_tables():
    rows, labels, times = _synthetic(80, entity_signal=True)
    db = _FakeDB()
    registry = _registry()
    with (
        patch("app.ml.churn_feature_ingest.list_churn_training_rows", return_value=_labelled(rows, labels, times)),
        patch.object(it, "get_model_registry", return_value=registry),
    ):
        result = await it.train_churn_risk_scorer(ORG, settings=Settings(), client=db)
    assert Settings().churn_entity_features_enabled is False
    assert db.queries == []
    assert "entity_features" not in result
    registry.add_version.assert_awaited_once()


@pytest.mark.asyncio
async def test_flag_on_refused_challenger_is_registered_not_deployed_and_baseline_still_trains():
    rows, labels, times = _synthetic(80, entity_signal=False)
    labelled = _labelled(rows, labels, times)
    # No bindings: every entity feature is missing, so nothing to beat the baseline with.
    db = _FakeDB(org_business_entity_bindings=[], entity_observations=[], entity_behavior_signals=[])
    registry = _registry()
    settings = Settings(churn_entity_features_enabled=True)
    with (
        patch("app.ml.churn_feature_ingest.list_churn_training_rows", return_value=labelled),
        patch.object(it, "get_model_registry", return_value=registry),
    ):
        result = await it.train_churn_risk_scorer(ORG, settings=settings, client=db)
    report = result["entity_features"]
    assert report["coverage"][UNMAPPED] == 80
    assert report["registration"]["deployed"] is False
    assert report["registration"]["deployment_reason"].startswith("not_deployed_")
    # Challenger version 1 refused; baseline version 2 then went through the usual gate.
    assert registry.add_version.await_count == 2
    deployed_versions = [c.args[1] for c in registry.deploy_version.await_args_list]
    assert 1 not in deployed_versions
    assert "feature_set" not in result


@pytest.mark.asyncio
async def test_advisory_gives_a_deployed_entity_model_its_features_only_with_flag_on():
    from app.services import churn_advisory_service as svc

    scorer = MagicMock()
    scorer._model = object()
    scorer.has_optional_features = MagicMock(return_value=True)
    scorer.predict_structured = AsyncMock(return_value={"status": "ok", "risk_score": 0.5, "risk_level": "medium"})
    unlabeled = [{"customer_id": "cust-a", "features": {"open_support_tickets": 1.0}}]
    extra = [{"obs_sentiment_mean": -0.5}]
    for flag, expect_enriched in ((False, False), (True, True)):
        scorer.predict_structured.reset_mock()
        with (
            patch.object(svc, "training_gate_status", return_value={"current": 40, "required": 30}),
            patch.object(svc, "list_churn_training_rows", return_value=[]),
            patch.object(svc, "list_unlabeled_churn_signal_rows", return_value=unlabeled),
            patch("app.ml.model_catalog.load_org_trained_catalog_model", AsyncMock(return_value=scorer)),
            patch("app.ml.churn_entity_features.load_entity_features", return_value=(extra, {})) as loader,
        ):
            await svc.build_churn_advisory_cards(
                ORG, settings=Settings(churn_entity_features_enabled=flag), client=_FakeDB()
            )
        assert loader.called is expect_enriched
        if not flag:
            # Flag off: the entity-trained model is never fed imputed features.
            assert not scorer.predict_structured.await_count
            continue
        sent = scorer.predict_structured.await_args.kwargs["customer_features"]
        assert ("obs_sentiment_mean" in sent) is expect_enriched
