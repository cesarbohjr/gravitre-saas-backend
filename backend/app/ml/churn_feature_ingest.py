"""Churn ML labeled feature contract — customer engagement signals for ChurnRiskScorer.

Hard rules:
- Writes training rows only; never contacts customers.
- Labels must be explicit churn/retain — not generic agent failures.

Storage (compatible with live agent_action_outcomes — no outcome_payload column):
- metric_name = churn_customer_signal
- metric_value_after = 1.0 if churned else 0.0
- confidence_note = JSON with FEATURE_KEYS + label_reason (+ advisory flag)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.ml.churn_scoring import FEATURE_KEYS, ChurnRiskScorer

CHURN_METRIC_NAME = "churn_customer_signal"
CHURN_ENTITY_TYPE = "customer"
CHURN_ACTION_TYPE = "churn_risk_label"

CHURN_LABEL_REASONS = frozenset({"cancel", "non_renew", "closed_lost", "churned"})
RETAIN_LABEL_REASONS = frozenset({"active", "renewed", "retained"})


def extract_churn_features(payload: dict[str, Any] | None) -> dict[str, float]:
    raw = payload if isinstance(payload, dict) else {}
    return {key: float(raw.get(key) or 0.0) for key in FEATURE_KEYS}


def features_usable(features: dict[str, float]) -> bool:
    return any(float(v) > 0 for v in features.values())


def resolve_churn_label(*, churned: bool | None = None, label_reason: str | None = None) -> bool | None:
    if churned is not None:
        return bool(churned)
    reason = str(label_reason or "").strip().lower()
    if reason in CHURN_LABEL_REASONS:
        return True
    if reason in RETAIN_LABEL_REASONS:
        return False
    return None


def _parse_note_payload(note: Any) -> dict[str, Any]:
    if isinstance(note, dict):
        return note
    text = str(note or "").strip()
    if not text.startswith("{"):
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_churn_outcome_row(
    *,
    org_id: str,
    customer_id: str,
    features: dict[str, Any],
    churned: bool,
    label_reason: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    feature_row = extract_churn_features(features)
    if not features_usable(feature_row):
        raise ValueError("churn features must include at least one positive FEATURE_KEYS value")
    now = datetime.now(timezone.utc).isoformat()
    reason = str(label_reason or ("churned" if churned else "retained")).strip().lower()
    note_payload = {
        **feature_row,
        "label_reason": reason,
        "churned": bool(churned),
        "advisory_only": True,
        "schema": "churn_customer_signal_v1",
    }
    return {
        "org_id": org_id,
        "agent_id": agent_id,
        "action_type": CHURN_ACTION_TYPE,
        "target_entity_type": CHURN_ENTITY_TYPE,
        "target_entity_id": str(customer_id),
        "metric_name": CHURN_METRIC_NAME,
        "action_taken_at": now,
        "measured_at": now,
        "metric_value_before": float(sum(feature_row.values())),
        "metric_value_after": 1.0 if churned else 0.0,
        "confidence_note": json.dumps(note_payload, separators=(",", ":")),
    }


def upsert_churn_training_example(
    client: Any,
    *,
    org_id: str,
    customer_id: str,
    features: dict[str, Any],
    churned: bool | None = None,
    label_reason: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    label = resolve_churn_label(churned=churned, label_reason=label_reason)
    if label is None:
        raise ValueError("churn label required (churned bool or label_reason)")
    row = build_churn_outcome_row(
        org_id=org_id,
        customer_id=customer_id,
        features=features,
        churned=label,
        label_reason=label_reason,
        agent_id=agent_id,
    )
    try:
        (
            client.table("agent_action_outcomes")
            .delete()
            .eq("org_id", org_id)
            .eq("metric_name", CHURN_METRIC_NAME)
            .eq("target_entity_type", CHURN_ENTITY_TYPE)
            .eq("target_entity_id", str(customer_id))
            .execute()
        )
    except Exception:  # noqa: BLE001
        pass
    inserted = client.table("agent_action_outcomes").insert(row).execute()
    data = (inserted.data or [row])[0] if hasattr(inserted, "data") else row
    return {"ok": True, "row": data, "churned": label}


def list_churn_training_rows(client: Any, org_id: str) -> list[dict[str, Any]]:
    rows = (
        client.table("agent_action_outcomes")
        .select("id, target_entity_id, confidence_note, metric_value_after, measured_at")
        .eq("org_id", org_id)
        .eq("metric_name", CHURN_METRIC_NAME)
        .eq("target_entity_type", CHURN_ENTITY_TYPE)
        .not_.is_("measured_at", "null")
        .execute()
        .data
        or []
    )
    usable: list[dict[str, Any]] = []
    for row in rows:
        payload = _parse_note_payload(row.get("confidence_note"))
        features = extract_churn_features(payload)
        if not features_usable(features):
            continue
        if "churned" in payload:
            churned = bool(payload.get("churned"))
        else:
            churned = float(row.get("metric_value_after") or 0.0) >= 0.5
        usable.append(
            {
                "id": row.get("id"),
                "customer_id": row.get("target_entity_id"),
                "features": features,
                "churned": churned,
                "outcome_success": not churned,
            }
        )
    return usable


def count_labeled_churn_examples(client: Any, org_id: str) -> int:
    return len(list_churn_training_rows(client, org_id))


def training_gate_status(client: Any, org_id: str) -> dict[str, Any]:
    current = count_labeled_churn_examples(client, org_id)
    required = ChurnRiskScorer.MIN_TRAINING_EXAMPLES
    return {
        "model": "churn_risk_scorer",
        "metric_name": CHURN_METRIC_NAME,
        "current": current,
        "required": required,
        "ready": current >= required,
        "advisory_only": True,
    }
