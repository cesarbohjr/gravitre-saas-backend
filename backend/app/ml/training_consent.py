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
    if model_name in {"multimodal_router", "domain_specific_llm", "diffusion_model"}:
        scope.update({
            "policy_version": 2,
            "processor": "OpenAI" if model_name != "multimodal_router" else "OpenAI and Deepgram (audio only)",
            "where": "Organization-authorized inputs are processed by the named external providers. Provider processing regions, retention and account terms apply; this permission does not assert regional residency.",
            "security": "Authorizes the stated provider-processing purpose for this organization only. It does not authorize federation, publication, connector writes or training on another organization's data. Media may contain personal information that text redaction cannot remove.",
            "when": "After this purpose-specific approval and current data, budget, model-policy and runtime checks pass.",
        })
        if model_name == "multimodal_router":
            scope.update({"processing_kind": "inference", "what": "Analyze authorized images, audio and sampled video frames",
                          "data": "Selected organization media bytes and the analysis prompt; audio is transcribed by Deepgram and the transcript is sent to OpenAI.",
                          "why": "Answer questions about approved media. This uses existing provider models and does not train a model."})
        elif model_name == "diffusion_model":
            scope.update({"processing_kind": "generation", "what": "Generate an image using the configured OpenAI image model",
                          "data": "The approved generation prompt. Generated images are stored privately in your configured organization artifact storage.",
                          "why": "Create a draft asset on an explicit request. This is a paid provider operation, not model training or permission to publish."})
        else:
            scope.update({"what": "Train and evaluate an organization-specific domain language model",
                          "data": "Explicitly bound, human-reviewed domain examples and held-out evaluation prompts/answers are sent to OpenAI.",
                          "why": "Improve a declared departmental task only when independent held-out results beat the base model. Account eligibility and provider model availability remain required."})
    if model_name == "federated_learning":
        scope.update({"policy_version": 3, "processing_kind": "federation", "sharing_scope": "cross_tenant_private_updates",
            "what": "Organization-level privacy-protected federated learning",
            "data": "Only clipped, noisy, cryptographically masked model updates from approved tenant runtimes. No raw documents, CRM records, prompts, outputs or unmasked per-tenant gradients.",
            "why": "Learn shared parameters across at least 100 explicitly consenting organizations under a reviewed, bounded privacy program.",
            "where": "A separately deployed Flower SecAgg+ runtime with mutual TLS and an independently signed deployment/privacy audit.",
            "security": "This is separate cross-tenant permission. Organization-only training approval is insufficient. Legal review, audited secure aggregation, composed differential privacy accounting and current per-tenant permission are mandatory.",
            "when": "Only after an independently signed privacy program is configured, the runtime attests to that deployment and at least 100 current tenant approvals exist. Each candidate needs 100 independent future retrieval-feedback observations in your organization within 14 days and must pass the local champion comparison before use. No manual activation toggle.",
            "controls": "Pause or revoke this permission in Intelligence. Current permission is checked before aggregate release and use of adopted federated artifacts. Previously released privacy-protected aggregates cannot be recalled, and completed privacy expenditure cannot be undone. Incomplete candidate validation expires after 14 days.",
        })
    if model_name == "federated_learning":
        try:
            from app.config import get_settings
            from app.ml.federated_learning import verified_privacy_profile
            profile, audit_digest = verified_privacy_profile(get_settings())
            scope["privacy_program"] = {key: profile[key] for key in ("program_id", "max_epsilon", "delta", "max_rounds", "privacy_unit", "adjacency", "audit_ref", "legal_review_ref", "expires_at")}
            scope["audit_digest"] = audit_digest
            scope["data"] += " Privacy program: " + json.dumps(scope["privacy_program"], sort_keys=True)
        except Exception:
            scope["privacy_program"] = None
            scope["security"] += " No verifiable privacy program is currently configured; approval is unavailable."
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
            and record.get("sharing_scope") == training_disclosure(model_name)["sharing_scope"])


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
    audit_digest = None
    if model_name == "federated_learning" and state == "approved":
        from app.ml.federated_learning import verified_privacy_profile
        _, audit_digest = verified_privacy_profile(settings)
        if disclosure.get("audit_digest") != audit_digest:
            raise ValueError("Privacy program changed; reload the current disclosure")
    event = {"state": state, "actor_id": actor_id, "recorded_at": datetime.now(timezone.utc).isoformat(),
             "scope_digest": scope_digest, "sharing_scope": disclosure["sharing_scope"], "policy_version": disclosure["policy_version"],
             **({"audit_digest": audit_digest} if audit_digest else {})}
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
    from app.ml.bound_training_data import collect_bound_records
    for name in ("graph_neural_network", "self_supervised_embeddings", "meta_learning", "sla_breach_predictor", "deal_loss_scorer"):
        required = {"meta_learning": 20, "sla_breach_predictor": 60, "deal_loss_scorer": 25}.get(name, 100)
        try:
            records = await asyncio.to_thread(collect_bound_records, org_id, name, settings, include_inputs=False)
        except Exception:
            observed[name] = {"signals_available": None, "min_required": required, "status": "unavailable"}
            continue
        observed[name] = {"signals_available": len(records), "min_required": required,
                          "status": "ready" if len(records) >= required else "insufficient_data"}
    from app.ml.domain_llm import collect_domain_corpus
    try:
        domain = await asyncio.to_thread(collect_domain_corpus, org_id, settings, include_inputs=False)
        observed["domain_specific_llm"] = {"signals_available": len(domain["training"]), "min_required": 1000, "status": "ready"}
    except Exception:
        observed["domain_specific_llm"] = {"signals_available": None, "min_required": 1000, "status": "unavailable"}
    try:
        from app.ml.federated_learning import verified_privacy_profile
        verified_privacy_profile(settings)
        observed["federated_learning"] = {"signals_available": None, "min_required": 100, "status": "ready"}
    except Exception:
        pass
    # Provider execution is request-driven, not training. Permission controls
    # remain available for review, without fabricating a data-detection event.
    try:
        response = await asyncio.to_thread(lambda: get_supabase_client(settings).table("organizations")
            .select("settings").eq("id", org_id).limit(1).execute())
        stored = safe_normalize_stored_dict(response.data[0].get("settings")) if response.data else {}
        requests = safe_normalize_stored_dict(stored.get("model_processing_requests"))
        for capability in ("multimodal_router", "diffusion_model"):
            request = safe_normalize_stored_dict(requests.get(capability))
            timestamp = datetime.fromisoformat(str(request.get("requested_at", "")).replace("Z", "+00:00")) if request else None
            if timestamp is not None and timestamp.tzinfo is not None and 0 <= (datetime.now(timezone.utc)-timestamp).total_seconds() <= 86400:
                observed[capability] = {"signals_available": None, "min_required": None, "status": "ready"}
    except Exception:
        pass
    inventory = []
    for name in (*CONSENT_MANAGED_MODELS, "multimodal_router", "diffusion_model", "federated_learning"):
        disclosure = training_disclosure(name)
        record = safe_normalize_stored_dict(consents.get(name))
        current = record.get("scope_digest") == disclosure["scope_digest"]
        state = record.get("state", "pending") if current else "pending"
        info = observed.get(name) or {}
        from app.ml.model_catalog import GRAVITRE_ML_CATALOG
        from app.ml.base import ModelStatus
        visible = (GRAVITRE_ML_CATALOG[name]["status"] == ModelStatus.TRAINED
                   or info.get("status") == "ready" or state != "pending")
        inventory.append({**disclosure, "consent_state": state, "permission_visible": visible,
                          "candidate_data_detected": info.get("status") in {"ready", "already_trained_recently"},
                          "observed_count": info.get("signals_available"), "required_count": info.get("min_required"),
                          "eligibility_note": "Detection is not proof of valid labels. Training revalidates data and promotion separately."})
    return {"models": inventory}


def record_processing_request(org_id: str, model_name: str, settings: Settings) -> None:
    """Record only that a governed request is waiting; never grant permission."""
    if model_name not in {"multimodal_router", "diffusion_model"}:
        return
    client = get_supabase_client(settings)
    response = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    if not response.data:
        return
    raw = response.data[0].get("settings")
    payload = safe_normalize_stored_dict(raw)
    original = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    requests = safe_normalize_stored_dict(payload.get("model_processing_requests"))
    requests[model_name] = {"requested_at": datetime.now(timezone.utc).isoformat()}
    payload["model_processing_requests"] = requests
    query = client.table("organizations").update({"settings": payload}).eq("id", org_id)
    query = query.is_("settings", "null") if raw is None else query.eq("settings", original)
    query.execute()
