"""Data adapters for bounded models, using the existing org registry and gates."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import numpy as np

from app.config import Settings, get_settings
from app.ml.base import ModelMetrics
from app.workflows.repository import get_supabase_client


def _measured_revenue(org_id: str, settings: Settings) -> list[dict[str, Any]]:
    rows = (get_supabase_client(settings).table("agent_action_outcomes")
            .select("metric_value_before,metric_value_after,action_type,measured_at")
            .eq("org_id", org_id).eq("metric_name", "deal_amount")
            .not_.is_("measured_at", "null").order("measured_at").limit(10000).execute().data or [])
    valid = []
    for row in rows:
        try:
            before, after = float(row["metric_value_before"]), float(row["metric_value_after"])
            measured = datetime.fromisoformat(str(row["measured_at"]).replace("Z", "+00:00"))
        except (TypeError, KeyError, ValueError):
            continue
        if not np.isfinite([before, after]).all() or not isinstance(row.get("action_type"), str) or measured.tzinfo is None:
            continue
        valid.append({**row, "before": before, "after": after, "measured": measured})
    return valid


async def train_bounded_outcome_model(org_id: str, model_name: str, *, settings: Settings | None = None) -> dict[str, Any]:
    from app.ml.intelligence_training import CATALOG_MODEL_NAMES, register_trained_artifact_detailed, registration_summary
    from app.ml.model_catalog import get_model_instance

    active = settings or get_settings()
    rows = await asyncio.to_thread(_measured_revenue, org_id, active)
    required = 500 if model_name == "world_model" else 100
    if len(rows) < required:
        return {"trained": False, "reason": "insufficient_measured_revenue_outcomes", "current": len(rows), "required": required}
    if model_name == "world_model":
        if (rows[-1]["measured"] - rows[0]["measured"]).days < 180:
            return {"trained": False, "reason": "six_months_measured_history_required"}
        actions = sorted({row["action_type"] for row in rows})
        if len(actions) > 32:
            return {"trained": False, "reason": "action_vocabulary_exceeds_bounded_model"}
        inputs = [{"deal_amount_before": row["before"],
                   **{f"action:{action}": float(row["action_type"] == action) for action in actions}} for row in rows]
        labels = [row["after"]-row["before"] for row in rows]
    elif model_name == "agentic_planning":
        inputs = [{"action": row["action_type"], "deal_amount_before": row["before"]} for row in rows]
        labels = [int(row["after"] > row["before"]) for row in rows]
    else:
        raise ValueError("Unsupported bounded outcome model")
    instance = get_model_instance(model_name)
    try:
        metrics: ModelMetrics = await instance.train(inputs, labels)
    except ValueError as exc:
        return {"trained": False, "reason": "validation_gate", "detail": str(exc)}
    registration = await register_trained_artifact_detailed(
        org_id, name=CATALOG_MODEL_NAMES[model_name], model_type=instance.model_type,
        base_model=model_name, artifact=instance.save(), metrics=metrics,
        description="Org-local observed deal_amount outcomes; advisory, not causal proof",
    )
    return {**registration_summary(registration), "metric_name": "deal_amount",
            "causal_proof": False, "training_samples": metrics.training_samples}


async def train_world_model(org_id: str, *, settings: Settings | None = None) -> dict[str, Any]:
    return await train_bounded_outcome_model(org_id, "world_model", settings=settings)


async def train_agentic_planning(org_id: str, *, settings: Settings | None = None) -> dict[str, Any]:
    return await train_bounded_outcome_model(org_id, "agentic_planning", settings=settings)


async def train_bound_catalog_model(org_id: str, model_name: str, *, settings: Settings | None = None) -> dict[str, Any]:
    from app.core.safe_dict import safe_normalize_stored_dict
    from app.ml.bound_training_data import collect_bound_records
    from app.ml.intelligence_training import CATALOG_MODEL_NAMES, register_trained_artifact_detailed, registration_summary
    from app.ml.model_catalog import get_model_instance
    from app.ml.training_consent import training_is_approved

    active = settings or get_settings()
    if not await training_is_approved(org_id, model_name, active):
        return {"trained": False, "reason": "training_permission_inactive"}
    records = await asyncio.to_thread(collect_bound_records, org_id, model_name, active)
    required = 20 if model_name == "meta_learning" else 100
    if len(records) < required:
        return {"trained": False, "reason": "eligible_bound_training_records_required", "current": len(records), "required": required}
    instance = get_model_instance(model_name)
    if model_name == "graph_neural_network":
        inputs = [{**safe_normalize_stored_dict(row["input"]),
                   "target_definition": row.get("training_target_definition")} for row in records]
        try:
            inputs_and_labels = sorted(zip(inputs, [int(row["expected_output"]) for row in records]),
                                       key=lambda pair: datetime.fromisoformat(str(pair[0].get("observed_at", "")).replace("Z", "+00:00")))
        except (ValueError, TypeError):
            return {"trained": False, "reason": "invalid_graph_timestamps"}
        inputs, labels = map(list, zip(*inputs_and_labels))
    elif model_name == "meta_learning":
        inputs, labels = [safe_normalize_stored_dict(row["input"]) for row in records], None
    else:
        inputs, labels = [row["input"] for row in records], None
    try:
        metrics = await instance.train(inputs, labels)
    except ValueError as exc:
        return {"trained": False, "reason": "validation_gate", "detail": str(exc)}
    registration = await register_trained_artifact_detailed(
        org_id, name=CATALOG_MODEL_NAMES[model_name], model_type=instance.model_type,
        base_model=model_name, artifact=instance.save(), metrics=metrics,
        description="Organization-local, explicitly bound training dataset; independent production outcome validation remains required",
    )
    return {**registration_summary(registration), "training_samples": metrics.training_samples}


async def train_graph_neural_network(org_id: str, *, settings: Settings | None = None) -> dict[str, Any]:
    return await train_bound_catalog_model(org_id, "graph_neural_network", settings=settings)


async def train_self_supervised_embeddings(org_id: str, *, settings: Settings | None = None) -> dict[str, Any]:
    return await train_bound_catalog_model(org_id, "self_supervised_embeddings", settings=settings)


async def train_meta_learning(org_id: str, *, settings: Settings | None = None) -> dict[str, Any]:
    return await train_bound_catalog_model(org_id, "meta_learning", settings=settings)
