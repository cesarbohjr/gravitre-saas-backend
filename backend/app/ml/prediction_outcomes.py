"""Phase 6: predictions checked against what actually happened.

A prediction about a subject (today: a customer's churn risk) is logged with a
horizon. The labeling job later resolves it from evidence, never by assuming:

- the outcome ledger: ``prediction_validated`` / ``prediction_missed`` events
  that name the prediction id;
- the source of record: a labelled churn signal for the same customer measured
  after the prediction and inside the horizon.

A prediction whose horizon passes without evidence becomes ``expired`` and is
left out of every metric; absence of a churn event is not a "retained" label.

``realized_metrics`` turns resolved predictions into the numbers a model owner
needs (count, base rate, accuracy at 0.5, Brier score, AUC when both classes
are present), split by model version.

Off unless ML_PREDICTION_OUTCOMES_ENABLED is true (needs migration
20261012060000).
"""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)

CHURN_HORIZON_DAYS = 90
LEDGER_LABELS = {"prediction_validated": "validated", "prediction_missed": "missed"}
MAX_PENDING_PER_RUN = 500


def outcomes_enabled(settings: Any) -> bool:
    return getattr(settings, "ml_prediction_outcomes_enabled", False) is True


def _parse(ts: Any) -> datetime | None:
    try:
        out = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None
    return out if out.tzinfo else out.replace(tzinfo=UTC)


def log_subject_prediction(
    client: Any,
    settings: Any,
    *,
    org_id: str,
    model_id: str,
    version: int,
    subject_type: str,
    subject_id: str,
    horizon_days: int,
    predicted_label: str,
    predicted_score: float | None,
    prediction: dict[str, Any],
) -> dict[str, Any]:
    """Log one checkable prediction, once per model version and subject while pending."""
    if not outcomes_enabled(settings):
        return {"skipped": "disabled"}
    existing = (
        client.table("model_predictions")
        .select("id")
        .eq("org_id", org_id)
        .eq("model_id", model_id)
        .eq("version", version)
        .eq("subject_type", subject_type)
        .eq("subject_id", subject_id)
        .eq("label_status", "pending")
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        return {"id": existing[0].get("id"), "deduplicated": True}
    row = {
        "org_id": org_id,
        "model_id": model_id,
        "version": version,
        "input_hash": f"{subject_type}:{subject_id}",
        "prediction": prediction,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "horizon_days": int(horizon_days),
        "predicted_label": predicted_label,
        "predicted_score": predicted_score,
        "label_status": "pending",
    }
    res = client.table("model_predictions").insert(row).execute()
    return {"id": ((res.data or [{}])[0]).get("id"), "deduplicated": False}


def _ledger_labels(client: Any, org_id: str, ids: list[str]) -> dict[str, dict[str, Any]]:
    if not ids:
        return {}
    rows = (
        client.table("intelligence_outcome_events")
        .select("prediction_id, outcome_event, created_at")
        .eq("org_id", org_id)
        .in_("prediction_id", ids)
        .in_("outcome_event", list(LEDGER_LABELS))
        .execute()
        .data
        or []
    )
    out: dict[str, dict[str, Any]] = {}
    for r in sorted(rows, key=lambda r: str(r.get("created_at"))):
        pid = str(r.get("prediction_id"))
        out.setdefault(pid, {
            "outcome_label": LEDGER_LABELS[str(r["outcome_event"])],
            "outcome_value": 1.0 if r["outcome_event"] == "prediction_validated" else 0.0,
            "outcome_source": "outcome_ledger",
            "outcome_observed_at": r.get("created_at"),
        })
    return out


def _churn_labels(client: Any, org_id: str, preds: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    from app.ml.churn_feature_ingest import (
        CHURN_ENTITY_TYPE,
        CHURN_METRIC_NAME,
        _parse_note_payload,
    )

    churn = [p for p in preds if p.get("subject_type") == CHURN_ENTITY_TYPE]
    if not churn:
        return {}
    rows = (
        client.table("agent_action_outcomes")
        .select("target_entity_id, confidence_note, metric_value_after, measured_at")
        .eq("org_id", org_id)
        .eq("metric_name", CHURN_METRIC_NAME)
        .eq("target_entity_type", CHURN_ENTITY_TYPE)
        .in_("target_entity_id", sorted({str(p["subject_id"]) for p in churn}))
        .execute()
        .data
        or []
    )
    by_customer: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_customer.setdefault(str(r.get("target_entity_id")), []).append(r)
    out: dict[str, dict[str, Any]] = {}
    for p in churn:
        made = _parse(p.get("created_at"))
        if made is None:
            continue
        end = made + timedelta(days=int(p.get("horizon_days") or CHURN_HORIZON_DAYS))
        for r in sorted(by_customer.get(str(p["subject_id"]), []), key=lambda r: str(r.get("measured_at"))):
            at = _parse(r.get("measured_at"))
            if at is None or not (made < at <= end):
                continue
            payload = _parse_note_payload(r.get("confidence_note"))
            churned = bool(payload["churned"]) if "churned" in payload else float(r.get("metric_value_after") or 0) >= 0.5
            out[str(p["id"])] = {
                "outcome_label": "churned" if churned else "retained",
                "outcome_value": 1.0 if churned else 0.0,
                "outcome_source": "agent_action_outcomes:churn_customer_signal",
                "outcome_observed_at": r.get("measured_at"),
            }
            break
    return out


def label_due_predictions(client: Any, org_id: str, *, now: datetime | None = None) -> dict[str, int]:
    """Resolve pending predictions that have evidence; expire those past their horizon."""
    now = now or datetime.now(UTC)
    pending = (
        client.table("model_predictions")
        .select("id, subject_type, subject_id, horizon_days, created_at")
        .eq("org_id", org_id)
        .eq("label_status", "pending")
        .order("created_at")
        .limit(MAX_PENDING_PER_RUN)
        .execute()
        .data
        or []
    )
    if not pending:
        return {"resolved": 0, "expired": 0, "pending": 0}
    labels = _ledger_labels(client, org_id, [str(p["id"]) for p in pending])
    for pid, label in _churn_labels(client, org_id, [p for p in pending if str(p["id"]) not in labels]).items():
        labels.setdefault(pid, label)
    counts = {"resolved": 0, "expired": 0, "pending": 0}
    stamp = now.isoformat()
    for p in pending:
        pid = str(p["id"])
        if pid in labels:
            update = {**labels[pid], "label_status": "resolved", "labeled_at": stamp}
            counts["resolved"] += 1
        else:
            made = _parse(p.get("created_at"))
            horizon = int(p.get("horizon_days") or 0)
            if made is None or now < made + timedelta(days=horizon):
                counts["pending"] += 1
                continue
            update = {"label_status": "expired", "labeled_at": stamp}
            counts["expired"] += 1
        (
            client.table("model_predictions")
            .update(update)
            .eq("org_id", org_id)
            .eq("id", pid)
            .eq("label_status", "pending")
            .execute()
        )
    return counts


def _auc(scores: list[float], labels: list[int]) -> float | None:
    pos = [s for s, y in zip(scores, labels, strict=True) if y == 1]
    neg = [s for s, y in zip(scores, labels, strict=True) if y == 0]
    if not pos or not neg:
        return None
    wins = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 4)


def realized_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Metrics on resolved binary predictions, per version. Expired rows are excluded."""
    by_version: dict[str, list[tuple[float, int]]] = {}
    expired: dict[str, int] = {}
    for r in rows:
        version = str(r.get("version"))
        if r.get("label_status") == "expired":
            expired[version] = expired.get(version, 0) + 1
            continue
        if r.get("label_status") != "resolved":
            continue
        score = r.get("predicted_score")
        value = r.get("outcome_value")
        if score is None or value is None or not math.isfinite(float(score)):
            continue
        by_version.setdefault(version, []).append((float(score), 1 if float(value) >= 0.5 else 0))
    out: dict[str, Any] = {}
    for version in sorted(set(by_version) | set(expired)):
        pairs = by_version.get(version, [])
        scores = [s for s, _ in pairs]
        labels = [y for _, y in pairs]
        n = len(pairs)
        out[version] = {
            "resolved": n,
            "expired": expired.get(version, 0),
            "base_rate": round(sum(labels) / n, 4) if n else None,
            "accuracy_at_0_5": round(sum(1 for s, y in pairs if (s >= 0.5) == bool(y)) / n, 4) if n else None,
            "brier": round(sum((s - y) ** 2 for s, y in pairs) / n, 4) if n else None,
            "auc_roc": _auc(scores, labels),
        }
    return out


def realized_report(client: Any, org_id: str, model_id: str) -> dict[str, Any]:
    rows = (
        client.table("model_predictions")
        .select("version, label_status, predicted_score, outcome_value")
        .eq("org_id", org_id)
        .eq("model_id", model_id)
        .in_("label_status", ["resolved", "expired"])
        .limit(5000)
        .execute()
        .data
        or []
    )
    return {"model_id": model_id, "versions": realized_metrics(rows)}


def run_labeling(client: Any) -> dict[str, dict[str, int]]:
    """One pass over every org with pending predictions."""
    rows = (
        client.table("model_predictions")
        .select("org_id")
        .eq("label_status", "pending")
        .limit(5000)
        .execute()
        .data
        or []
    )
    results: dict[str, dict[str, int]] = {}
    for org_id in sorted({str(r["org_id"]) for r in rows if r.get("org_id")}):
        try:
            results[org_id] = label_due_predictions(client, org_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("prediction_labeling_failed org_id=%s error=%s", org_id, type(exc).__name__)
    return results


def churn_prediction_payload(prediction: dict[str, Any]) -> tuple[str, float | None, dict[str, Any]]:
    score = prediction.get("risk_score")
    try:
        value = float(score) if score is not None else None
    except (TypeError, ValueError):
        value = None
    label = "churn" if value is not None and value >= 0.5 else "retain"
    return label, value, safe_normalize_stored_dict(prediction)
