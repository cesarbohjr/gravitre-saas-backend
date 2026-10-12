"""Phase 6: checkable predictions, evidence-only labels, realized metrics, time splits."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.ml import prediction_outcomes as po
from app.ml.splits import time_split
from tests.services.fake_supabase_db import FakeSupabaseDB

ORG = "org-1"
ON = SimpleNamespace(ml_prediction_outcomes_enabled=True)
NOW = datetime(2026, 10, 12, tzinfo=UTC)


def _ago(days: float) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def _log(db, subject: str, **kw):
    return po.log_subject_prediction(
        db, ON, org_id=ORG, model_id="m1", version=kw.get("version", 1), subject_type="customer",
        subject_id=subject, horizon_days=90, predicted_label="churn", predicted_score=kw.get("score", 0.8),
        prediction={"risk_score": kw.get("score", 0.8)},
    )


def test_logging_is_off_by_default_and_once_per_pending_subject():
    db = FakeSupabaseDB()
    assert po.log_subject_prediction(
        db, SimpleNamespace(), org_id=ORG, model_id="m1", version=1, subject_type="customer", subject_id="c1",
        horizon_days=90, predicted_label="churn", predicted_score=0.8, prediction={},
    ) == {"skipped": "disabled"}
    _log(db, "c1")
    assert _log(db, "c1")["deduplicated"] is True
    _log(db, "c1", version=2)
    rows = db.tables["model_predictions"]
    assert len(rows) == 2 and all(r["label_status"] == "pending" for r in rows)


def _pending(pid: str, subject: str, made_days_ago: float, horizon: int = 90) -> dict:
    return {"id": pid, "org_id": ORG, "subject_type": "customer", "subject_id": subject, "horizon_days": horizon,
            "created_at": _ago(made_days_ago), "label_status": "pending", "predicted_score": 0.8, "version": 1}


def test_labels_come_from_evidence_only():
    db = FakeSupabaseDB()
    db.tables["model_predictions"] = [
        _pending("p-ledger", "c0", 10),
        _pending("p-churned", "c1", 30),
        _pending("p-before", "c2", 30),
        _pending("p-expired", "c3", 120),
        _pending("p-wait", "c4", 10),
    ]
    db.tables["intelligence_outcome_events"] = [
        {"org_id": ORG, "prediction_id": "p-ledger", "outcome_event": "prediction_missed", "created_at": _ago(1)},
    ]
    db.tables["agent_action_outcomes"] = [
        {"org_id": ORG, "metric_name": "churn_customer_signal", "target_entity_type": "customer", "target_entity_id": "c1",
         "confidence_note": json.dumps({"churned": True}), "measured_at": _ago(5)},
        # Measured before the prediction was made: not a label for it.
        {"org_id": ORG, "metric_name": "churn_customer_signal", "target_entity_type": "customer", "target_entity_id": "c2",
         "confidence_note": json.dumps({"churned": False}), "measured_at": _ago(40)},
    ]
    counts = po.label_due_predictions(db, ORG, now=NOW)
    assert counts == {"resolved": 2, "expired": 1, "pending": 2}
    by_id = {r["id"]: r for r in db.tables["model_predictions"]}
    assert by_id["p-ledger"]["outcome_label"] == "missed" and by_id["p-ledger"]["outcome_source"] == "outcome_ledger"
    assert by_id["p-churned"]["outcome_label"] == "churned" and by_id["p-churned"]["outcome_value"] == 1.0
    assert by_id["p-before"]["label_status"] == "pending"
    assert by_id["p-expired"]["label_status"] == "expired" and "outcome_label" not in by_id["p-expired"]
    assert by_id["p-wait"]["label_status"] == "pending"


def test_realized_metrics_exclude_expired_and_report_per_version():
    rows = [
        {"version": 1, "label_status": "resolved", "predicted_score": 0.9, "outcome_value": 1.0},
        {"version": 1, "label_status": "resolved", "predicted_score": 0.2, "outcome_value": 0.0},
        {"version": 1, "label_status": "resolved", "predicted_score": 0.6, "outcome_value": 0.0},
        {"version": 1, "label_status": "expired", "predicted_score": 0.9, "outcome_value": None},
        {"version": 2, "label_status": "resolved", "predicted_score": 0.7, "outcome_value": 1.0},
    ]
    m = po.realized_metrics(rows)
    assert m["1"]["resolved"] == 3 and m["1"]["expired"] == 1
    assert m["1"]["accuracy_at_0_5"] == round(2 / 3, 4)
    assert m["1"]["auc_roc"] == 1.0
    assert m["1"]["brier"] == round((0.01 + 0.04 + 0.36) / 3, 4)
    assert m["2"]["auc_roc"] is None  # one class only


def test_time_split_holds_out_the_latest_and_refuses_bad_input():
    stamps = [_ago(100 - i) for i in range(10)]
    labels = [0, 1] * 5
    train, hold, start = time_split(stamps, labels)
    assert hold == [8, 9] and start == stamps[8] and set(train) == set(range(8))
    assert time_split(stamps[:-1] + ["not a date"], labels) is None
    assert time_split(stamps, [0] * 8 + [1, 1]) is None  # holdout has one class


def test_churn_training_uses_time_split_when_given_times():
    from app.ml.churn_scoring import ChurnRiskScorer

    rows = [{"days_since_last_activity": i % 7, "open_support_tickets": i % 3} for i in range(40)]
    labels = [i % 2 for i in range(40)]
    stamps = [_ago(200 - i) for i in range(40)]
    timed = asyncio.run(ChurnRiskScorer().train(rows, labels, observed_at=stamps))
    assert timed.custom_metrics["split"] == "time" and timed.validation_samples == 8
    plain = asyncio.run(ChurnRiskScorer().train(rows, labels))
    assert plain.custom_metrics == {"split": "random"}


def test_churn_advisory_logs_only_with_flag_and_registry_ref():
    from app.services.churn_advisory_service import _log_checkable_prediction

    db = FakeSupabaseDB()
    scorer = SimpleNamespace(registry_ref={"model_id": "m1", "version": 3})
    _log_checkable_prediction(db, SimpleNamespace(), ORG, scorer, "c1", {"risk_score": 0.7})
    _log_checkable_prediction(db, ON, ORG, SimpleNamespace(), "c1", {"risk_score": 0.7})
    assert db.tables.get("model_predictions") is None
    _log_checkable_prediction(db, ON, ORG, scorer, "c1", {"risk_score": 0.7})
    row = db.tables["model_predictions"][0]
    assert (row["version"], row["predicted_label"], row["predicted_score"], row["horizon_days"]) == (3, "churn", 0.7, 90)


def test_labeling_scheduler_is_off_by_default(monkeypatch):
    from app.schedulers import prediction_labeling_scheduler as sched

    monkeypatch.setattr(sched, "get_settings", lambda: SimpleNamespace())
    assert sched.start_prediction_labeling_scheduler() is None


@pytest.mark.parametrize("score,label", [(0.5, "churn"), (0.49, "retain"), (None, "retain")])
def test_churn_payload_label(score, label):
    assert po.churn_prediction_payload({"risk_score": score})[0] == label
