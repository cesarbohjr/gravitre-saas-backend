"""Read explicitly bound tenant training data; never scrape arbitrary documents.

Uses existing Model Studio model targets, admin-created training bindings and
training_records. Missing tables, target, binding or provenance fail closed.
"""
from __future__ import annotations

from typing import Any

from app.config import Settings
from app.core.safe_dict import safe_normalize_stored_dict
from app.workflows.repository import get_supabase_client


def collect_bound_records(org_id: str, model_name: str, settings: Settings, *, include_inputs: bool = True) -> list[dict[str, Any]]:
    if model_name not in {"graph_neural_network", "self_supervised_embeddings", "meta_learning", "sla_breach_predictor", "deal_loss_scorer"} or not org_id:
        raise ValueError("Supported model and organization required")
    db = get_supabase_client(settings)
    targets = (db.table("trained_models").select("id").eq("org_id", org_id)
               .eq("base_model", model_name).limit(100).execute().data or [])
    target_ids = [row["id"] for row in targets if row.get("id")]
    if not target_ids:
        return []
    bindings = (db.table("training_dataset_bindings").select("dataset_id,metadata")
                .eq("org_id", org_id).eq("target_type", "model").eq("purpose", "training")
                .in_("target_id", target_ids).limit(100).execute().data or [])
    # Binding metadata is a declared dataset contract, not proof of model quality.
    datasets = []
    definitions = set()
    expected_target = {"sla_breach_predictor": "sla_breached", "deal_loss_scorer": "deal_lost"}.get(model_name)
    for binding in bindings:
        metadata = safe_normalize_stored_dict(binding.get("metadata"))
        if expected_target is not None and metadata.get("target_definition") != expected_target:
            continue
        if (metadata.get("model_name") == model_name and metadata.get("schema_version") == 1
                and isinstance(metadata.get("target_definition"), str) and metadata["target_definition"].strip()):
            datasets.append(binding["dataset_id"])
            definitions.add(metadata["target_definition"].strip())
    if len(definitions) > 1:
        raise ValueError("Bound datasets must use one consistent target definition")
    if not datasets:
        return []
    columns = "id,input,expected_output,metadata,created_at" if include_inputs else "id,expected_output,metadata"
    rows = (db.table("training_records").select(columns)
            .eq("org_id", org_id).in_("dataset_id", list(set(datasets)))
            .order("created_at", desc=True).limit(1000).execute().data or [])
    valid = []
    for row in rows:
        metadata = safe_normalize_stored_dict(row.get("metadata"))
        if metadata.get("synthetic") is not False or not isinstance(metadata.get("source_ref"), str) or not metadata["source_ref"].strip():
            continue
        if model_name in {"graph_neural_network", "meta_learning", "sla_breach_predictor", "deal_loss_scorer"} and metadata.get("label_source") != "human_reviewed":
            continue
        if model_name in {"graph_neural_network", "sla_breach_predictor", "deal_loss_scorer"} and row.get("expected_output") not in {"0", "1"}:
            continue
        if include_inputs and (not isinstance(row.get("input"), str) or not row["input"].strip() or len(row["input"]) > 65536):
            continue
        valid.append(row)
    # Monitor the newest bounded window so new imports can unblock a model,
    # then restore source order for downstream chronological validation.
    return list(reversed(valid))
