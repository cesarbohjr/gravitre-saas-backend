"""Execution evidence in the existing prediction ledger, without input/output data.

An execution record is not accuracy, business outcome, or downstream-consumption
proof. Diagnostic requests are not recorded as normal backend use.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.config import Settings
from app.core.io_pool import run_io
from app.core.safe_dict import safe_normalize_stored_dict
from app.workflows.repository import get_supabase_client

PROOF_TYPE = "validated_catalog_execution_v1"
SOURCES = frozenset({"internal", "intelligence_router", "predictive_operations", "memory_review"})


async def record_execution(org_id: str, model_name: str, registry_ref: Any, latency_ms: int, source: str) -> dict[str, Any]:
    trace_id = uuid4().hex
    result = {"trace_id": trace_id, "recorded": False, "scope": "inference_execution_only"}
    if not isinstance(source, str) or source not in SOURCES or not isinstance(registry_ref, dict):
        return result
    model_id, version = registry_ref.get("model_id"), registry_ref.get("version")
    if not isinstance(model_id, str) or not model_id or type(version) is not int or version < 1:
        return result
    from app.ml.registry import get_model_registry
    try:
        await asyncio.wait_for(get_model_registry().log_prediction(
            org_id=org_id, model_id=model_id, version=version,
            input_hash=f"invocation:{trace_id}",
            prediction={"execution_evidence": {"proof_type": PROOF_TYPE, "catalog_model": model_name,
                                                "source": source, "trace_id": trace_id,
                                                "scope": "inference_execution_only"}},
            latency_ms=latency_ms,
        ), timeout=.2)
        result["recorded"] = True
    except Exception:
        # Observability failure must not hide a usable prediction. A read-side
        # evidence claim requires an actual stored record, never this attempt.
        pass
    return result


def _read_recent(org_id: str, settings: Settings) -> list[dict[str, Any]]:
    since = datetime.now(timezone.utc)-timedelta(hours=24)
    return (get_supabase_client(settings).table("model_predictions")
            .select("model_id,version,created_at,execution_evidence:prediction->execution_evidence")
            .eq("org_id", org_id).gte("created_at", since.isoformat())
            .order("created_at", desc=True).limit(200).execute().data or [])


async def recent_execution_evidence(org_id: str, settings: Settings) -> dict[str, dict[str, Any]]:
    if not org_id:
        raise ValueError("Organization required")
    rows = await run_io(_read_recent, org_id, settings)
    result = {}
    now = datetime.now(timezone.utc)
    for row in rows:
        proof = safe_normalize_stored_dict(row.get("execution_evidence"))
        name = proof.get("catalog_model")
        source = proof.get("source")
        try:
            timestamp = datetime.fromisoformat(str(row.get("created_at", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if (not isinstance(name, str) or name in result or proof.get("proof_type") != PROOF_TYPE
                or not isinstance(source, str) or source not in SOURCES or timestamp.tzinfo is None
                or not now-timedelta(hours=24) <= timestamp <= now):
            continue
        result[name] = {"model_id": row.get("model_id"), "version": row.get("version"),
                        "recorded_at": timestamp.isoformat(), "source": proof["source"], "trace_id": proof.get("trace_id"),
                        "scope": "inference_execution_only", "downstream_consumption": "not_verified"}
    return result
