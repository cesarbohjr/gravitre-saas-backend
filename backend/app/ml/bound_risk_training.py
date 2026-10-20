"""Train existing risk models from explicitly bound, labeled tenant records.

Aggregate outcome metrics are never ticket/deal labels. No new ingestion store,
model, scheduler or engine. Uses Model Studio's existing binding and registry.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from sklearn.model_selection import TimeSeriesSplit

from app.config import Settings, get_settings
from app.core.safe_dict import safe_normalize_stored_dict


def _timestamp(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timezone-bearing feature and outcome timestamps required")
    return parsed


def risk_training_rows(records: list[dict[str, Any]], *, include_split: bool = False) -> tuple:
    rows = []
    ids = set()
    for record in records:
        payload = safe_normalize_stored_dict(record.get("input"))
        entity_id = payload.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id or entity_id in ids:
            raise ValueError("Distinct ticket/deal entity identifiers required")
        ids.add(entity_id)
        observed, resolved = _timestamp(payload.get("observed_at")), _timestamp(payload.get("outcome_observed_at"))
        if not observed < resolved <= datetime.now(timezone.utc):
            raise ValueError("Features must precede independently resolved outcomes; future labels are invalid")
        if record.get("expected_output") not in {"0", "1"}:
            raise ValueError("Explicit binary outcome labels required")
        features = safe_normalize_stored_dict(payload.get("features"))
        if not features:
            raise ValueError("Real ticket/deal features required")
        rows.append((observed, resolved, features, int(record["expected_output"])))
    rows.sort(key=lambda row: row[0])
    if not rows:
        return ([], [], {"training_split": 0, "calibration_splits": []}) if include_split else ([], [])
    split = int(len(rows)*.8)
    # Purge labels not yet known at the first holdout observation, rather than
    # permanently rejecting otherwise valid series with delayed outcomes.
    training = [row for row in rows[:split] if row[1] < rows[split][0]]
    heldout = rows[split:]
    if len(training) < 4:
        raise ValueError("Insufficient resolved training history before holdout")
    folds = []
    for train_indices, calibration_indices in TimeSeriesSplit(n_splits=3).split(training):
        as_of = training[int(calibration_indices[0])][0]
        purged = [int(i) for i in train_indices if training[int(i)][1] < as_of]
        if not purged:
            raise ValueError("Insufficient resolved history before calibration")
        folds.append((purged, calibration_indices))
    combined = training + heldout
    inputs, labels = [row[2] for row in combined], [row[3] for row in combined]
    if include_split:
        return inputs, labels, {"training_split": len(training), "calibration_splits": folds}
    return inputs, labels



async def train_bound_risk_model(org_id: str, model_name: str, *, settings: Settings | None = None) -> dict[str, Any]:
    from app.ml.bound_training_data import collect_bound_records
    from app.ml.intelligence_training import CATALOG_MODEL_NAMES, register_trained_artifact_detailed, registration_summary
    from app.ml.model_catalog import get_model_instance
    from app.ml.training_consent import training_is_approved

    if model_name not in {"sla_breach_predictor", "deal_loss_scorer"} or not org_id:
        raise ValueError("Supported risk model and organization required")
    active = settings or get_settings()
    if not await training_is_approved(org_id, model_name, active):
        return {"trained": False, "reason": "training_permission_inactive"}
    try:
        records = await asyncio.to_thread(collect_bound_records, org_id, model_name, active)
    except Exception:
        return {"trained": False, "reason": "bound_training_data_unavailable"}
    instance = get_model_instance(model_name)
    if len(records) < instance.MIN_TRAINING_EXAMPLES:
        return {"trained": False, "reason": "eligible_bound_training_records_required", "current": len(records), "required": instance.MIN_TRAINING_EXAMPLES}
    try:
        inputs, labels, split_parameters = risk_training_rows(records, include_split=True)
        metrics = await instance.train(inputs, labels, **split_parameters)
    except (ValueError, TypeError, KeyError):
        return {"trained": False, "reason": "risk_data_or_temporal_validation_failed"}
    registration = await register_trained_artifact_detailed(
        org_id, name=CATALOG_MODEL_NAMES[model_name], model_type=instance.model_type,
        base_model=model_name, artifact=instance.save(), metrics=metrics,
        description="Explicit labeled tenant entities; chronological held-out evaluation and temporal sigmoid calibration",
    )
    return {**registration_summary(registration), "training_samples": metrics.training_samples,
            "validation_samples": metrics.validation_samples, "evaluation": metrics.custom_metrics}
