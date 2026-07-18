"""Churn ML labeled feature contract — customer engagement signals for ChurnRiskScorer.

Hard rules:
- Writes training rows only; never contacts customers.
- Labels must be explicit churn/retain — not generic agent outcome_success.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.ml.churn_scoring import FEATURE_KEYS, ChurnRiskScorer

CHURN_METRIC_NAME = "churn_customer_signal"
CHURN_ENTITY_TYPE = "customer"
CHURN_ACTION_TYPE = "churn_risk_label"

# Explicit churn reasons (stored in outcome_payload for audit; not model features).
CHURN_LABEL_REASONS = frozenset({"cancel", "non_renew", "closed_lost", "churned"})
RETAIN_LABEL_REASONS = frozenset({"active", "renewed", "retained"})


def extract_churn_features(payload: dict[str, Any] | None) -> dict[str, float]:
    raw = payload if isinstance(payload, dict) else {}
    return {key: float(raw.get(key) or 0.0) for key in FEATURE_KEYS}


def features_usable(features: dict[str, float]) -> bool:
    return any(float(v) > 0 for v in features.values())


def resolve_churn_label(*, churned: bool | None = None, label_reason: str | None = None) -> bool | None:
    """Return True if churned, False if retained, None if unknown."""
    if churned is not None:
        return bool(churned)
    reason = str(label_reason or "").strip().lower()
    if reason in CHURN_LABEL_REASONS:
        return True
    if reason in RETAIN_LABEL_REASONS:
        return False
    return None


def build_churn_outcome_row(
    *,
    org_id: str,
    customer_id: str,
    features: dict[str, Any],
    churned: bool,
    label_reason: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """Build an agent_action_outcomes row for churn training."""
    feature_row = extract_churn_features(features)
    if not features_usable(feature_row):
        raise ValueError("churn features must include at least one positive FEATURE_KEYS value")
    now = datetime.now(timezone.utc).isoformat()
    reason = str(label_reason or ("churned" if churned else "retained")).strip().lower()
    return {
        "org_id": org_id,
        "agent_id": agent_id,
        "action_type": CHURN_ACTION_TYPE,
        "target_entity_type": CHURN_ENTITY_TYPE,
        "target_entity_id": str(customer_id),
        "metric_name": CHURN_METRIC_NAME,
        "action_taken_at": now,
        "measured_at": now,
        "outcome_success": not bool(churned),  # success = retained
        "outcome_payload": {
            **feature_row,
            "label_reason": reason,
            "churned": bool(churned),
            "advisory_only": True,
        },
        "confidence_note": "Labeled churn customer signal — advisory training only; never auto-contacts.",
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
    """Insert (or replace-by-reinsert) a labeled churn training example."""
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
    # Soft replace: delete prior signal for same customer, then insert.
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
        .select("id, target_entity_id, outcome_payload, outcome_success, measured_at")
        .eq("org_id", org_id)
        .eq("metric_name", CHURN_METRIC_NAME)
        .eq("target_entity_type", CHURN_ENTITY_TYPE)
        .not_.is_("outcome_success", "null")
        .execute()
        .data
        or []
    )
    usable: list[dict[str, Any]] = []
    for row in rows:
        features = extract_churn_features(row.get("outcome_payload"))
        if not features_usable(features):
            continue
        usable.append(
            {
                "id": row.get("id"),
                "customer_id": row.get("target_entity_id"),
                "features": features,
                "churned": not bool(row.get("outcome_success")),
                "outcome_success": row.get("outcome_success"),
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
