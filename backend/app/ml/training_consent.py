"""Versioned, org-scoped consent for background model training.

Consent is stored in existing organization settings using compare-and-swap;
no schema or production migration is required. Consent authorizes the stated
training purpose only, never action execution or cross-tenant sharing.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.core.safe_dict import safe_normalize_stored_dict
from app.workflows.repository import get_supabase_client

SETTINGS_KEY = "model_training_consents"
POLICY_VERSION = 1


def training_disclosure(model_name: str) -> dict[str, Any]:
    from app.ml.model_catalog import GRAVITRE_ML_CATALOG
    if model_name not in GRAVITRE_ML_CATALOG:
        raise ValueError("Unknown model")
    meta = GRAVITRE_ML_CATALOG[model_name]
    scope = {
        "policy_version": POLICY_VERSION, "model_name": model_name,
        "what": model_name.replace("_", " "),
        "why": ", ".join(meta.get("use_cases") or [model_name]).replace("_", " "),
        "data": meta.get("activation") or meta.get("min_data") or meta.get("note") or "Validated organization-local examples",
        "when": "After your approval, on the next scheduled learning run, if validation still passes.",
        "where": "Your organization's configured Gravitre backend and model artifact storage. Physical region is deployment-specific; this approval does not change it.",
        "security": "Organization-only training. No cross-organization sharing is authorized. Existing access, retention, and action-approval policies remain in force.",
        "controls": "Pause, resume, or revoke under Intelligence → Training permissions. Pausing stops future training and new inference with these automatically managed models; in-flight work may finish. It does not delete existing artifacts.",
        "sharing_scope": "organization_only",
    }
    digest = hashlib.sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()
    return {**scope, "scope_digest": digest}


def load_training_consents(org_id: str, settings: Settings) -> dict[str, Any]:
    response = (get_supabase_client(settings).table("organizations").select("settings")
                .eq("id", org_id).limit(1).execute())
    if not response.data:
        raise ValueError("Organization not found")
    payload = safe_normalize_stored_dict(response.data[0].get("settings"))
    return safe_normalize_stored_dict(payload.get(SETTINGS_KEY))


def consent_is_approved(consents: dict[str, Any], model_name: str) -> bool:
    record = safe_normalize_stored_dict(consents.get(model_name))
    return (record.get("state") == "approved"
            and record.get("scope_digest") == training_disclosure(model_name)["scope_digest"]
            and record.get("sharing_scope") == "organization_only")


async def training_is_approved(org_id: str, model_name: str, settings: Settings) -> bool:
    try:
        consents = await asyncio.to_thread(load_training_consents, org_id, settings)
        return consent_is_approved(consents, model_name)
    except Exception:
        return False


def save_training_consent(org_id: str, model_name: str, actor_id: str, state: str,
                          scope_digest: str, settings: Settings) -> dict[str, Any]:
    if not actor_id or state not in {"approved", "paused", "revoked", "deferred"}:
        raise ValueError("Valid actor and consent state required")
    disclosure = training_disclosure(model_name)
    if scope_digest != disclosure["scope_digest"]:
        raise ValueError("Training disclosure changed; reload before approving")
    client = get_supabase_client(settings)
    response = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    if not response.data:
        raise ValueError("Organization not found")
    raw = response.data[0].get("settings")
    payload = safe_normalize_stored_dict(raw)
    original = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    consents = safe_normalize_stored_dict(payload.get(SETTINGS_KEY))
    previous = safe_normalize_stored_dict(consents.get(model_name))
    history = previous.get("history") if isinstance(previous.get("history"), list) else []
    event = {"state": state, "actor_id": actor_id, "recorded_at": datetime.now(timezone.utc).isoformat(),
             "scope_digest": scope_digest, "sharing_scope": "organization_only", "policy_version": POLICY_VERSION}
    consents[model_name] = {**event, "history": [*history[-19:], event]}
    payload[SETTINGS_KEY] = consents
    query = client.table("organizations").update({"settings": payload}).eq("id", org_id)
    # Avoid overwriting unrelated settings changed concurrently (including a
    # revocation). PostgREST jsonb equality performs structural comparison.
    query = query.is_("settings", "null") if raw is None else query.eq("settings", original)
    saved = query.execute()
    if not saved.data:
        raise ValueError("Organization settings changed concurrently; reload and retry")
    return {"model_name": model_name, **event}


async def training_permission_inventory(org_id: str, settings: Settings) -> dict[str, Any]:
    from app.ml.advanced_training import _measured_revenue
    from app.ml.automatic_training import CONSENT_MANAGED_MODELS
    from app.services.training_signal_service import get_training_signal_service

    consents = await asyncio.to_thread(load_training_consents, org_id, settings)
    readiness = await get_training_signal_service(settings).get_training_readiness(org_id)
    observed = readiness.get("by_model") or {}
    rows = await asyncio.to_thread(_measured_revenue, org_id, settings)
    observed["agentic_planning"] = {"signals_available": len(rows), "min_required": 100,
                                   "status": "ready" if len(rows) >= 100 else "insufficient_data"}
    world_ready = len(rows) >= 500 and (rows[-1]["measured"]-rows[0]["measured"]).days >= 180
    observed["world_model"] = {"signals_available": len(rows), "min_required": 500,
                              "status": "ready" if world_ready else "insufficient_data"}
    from app.ml.model_catalog import _count_org_data_points
    for name, key, required in [("query_clusterer", "logged_queries", 40),
                                 ("memory_promotion_scorer", "resolved_candidates", 15)]:
        counts = await asyncio.to_thread(_count_org_data_points, org_id, name, settings)
        count = int((counts.get("data_counts") or {}).get(key) or 0)
        observed[name] = {"signals_available": count, "min_required": required,
                          "status": "ready" if count >= required else "insufficient_data"}
    observed["retrieval_memory_learner"] = observed.get("retrieval_ranker") or {}
    inventory = []
    for name in CONSENT_MANAGED_MODELS:
        disclosure = training_disclosure(name)
        record = safe_normalize_stored_dict(consents.get(name))
        current = record.get("scope_digest") == disclosure["scope_digest"]
        state = record.get("state", "pending") if current else "pending"
        info = observed.get(name) or {}
        inventory.append({**disclosure, "consent_state": state,
                          "candidate_data_detected": info.get("status") in {"ready", "already_trained_recently"},
                          "observed_count": info.get("signals_available"), "required_count": info.get("min_required"),
                          "eligibility_note": "Detection is not proof of valid labels. Training revalidates data and promotion separately."})
    return {"models": inventory}
