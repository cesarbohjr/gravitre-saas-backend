"""Shared fail-closed provider controls for advanced catalog capabilities.

Reuses organization settings, model policy, Redis coordination and the existing
provider clients. Reserved upper bounds are spending controls, never billing or
claims about actual provider charges.
"""
from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any

from app.core.safe_dict import safe_normalize_stored_dict
from app.ml.training_consent import training_is_approved
from app.services.ai_guardrails import enforce_rate_limit
from app.services.model_policy_service import assert_model_allowed, load_org_model_policy
from app.workflows.repository import get_supabase_client


def processing_policy(org_id: str, capability: str, settings: Any) -> dict[str, Any]:
    client = get_supabase_client(settings)
    response = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    if not response.data:
        raise ValueError("Organization processing policy unavailable")
    stored = safe_normalize_stored_dict(response.data[0].get("settings"))
    policies = safe_normalize_stored_dict(stored.get("advancedProcessingPolicies"))
    policy = safe_normalize_stored_dict(policies.get(capability))
    model = policy.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Configured provider model required")
    expiry = datetime.fromisoformat(str(policy.get("pricing_valid_until", "")).replace("Z", "+00:00"))
    if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
        raise ValueError("Current reviewed provider cost bound required")
    for key in ("max_request_usd", "monthly_limit_usd"):
        value = policy.get(key)
        if type(value) not in {int, float} or not math.isfinite(value) or value <= 0:
            raise ValueError("Positive finite provider cost bounds required")
    if policy["max_request_usd"] > policy["monthly_limit_usd"]:
        raise ValueError("Request bound exceeds organization budget")
    assert_model_allowed(load_org_model_policy(client, org_id), provider="openai", model=model)
    enforce_rate_limit(org_id, settings)
    return policy


async def require_permission(org_id: str, capability: str, settings: Any) -> None:
    if not isinstance(org_id, str) or not org_id.strip() or not await training_is_approved(org_id, capability, settings):
        from app.ml.training_consent import record_processing_request
        import asyncio
        try:
            await asyncio.to_thread(record_processing_request, org_id, capability, settings)
        except Exception:
            pass  # Detection persistence can fail, but permission still denies.
        raise ValueError("Current purpose-specific provider permission required; review the waiting request in Intelligence")


def reserve_provider_budget(redis: Any, org_id: str, capability: str, policy: dict[str, Any], operation_id: str, settings: Any = None) -> None:
    """Durable CAS cost reservations in existing organization settings.

    Redis still coordinates dispatch, but losing its cache cannot reset the
    monthly cost ledger. This records reviewed upper bounds, never invoices.
    """
    if redis is None:
        raise ValueError("Provider dispatch coordination unavailable")
    from app.config import get_settings
    import json
    settings = settings or get_settings()
    client = get_supabase_client(settings)
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    cost = math.ceil(policy["max_request_usd"] * 1_000_000)
    limit = math.floor(policy["monthly_limit_usd"] * 1_000_000)
    operation = hashlib.sha256(operation_id.encode()).hexdigest()
    for _ in range(3):
        response = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
        if not response.data:
            raise ValueError("Organization provider cost ledger unavailable")
        raw = response.data[0].get("settings")
        payload = safe_normalize_stored_dict(raw)
        original = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        ledger = safe_normalize_stored_dict(payload.get("advanced_provider_cost_reservations"))
        period = safe_normalize_stored_dict(ledger.get(month))
        operations = safe_normalize_stored_dict(period.get(capability))
        if any(type(value) is not int or value <= 0 for value in operations.values()):
            raise ValueError("Provider reservation ledger is invalid")
        if operation in operations:
            return
        if len(operations) >= 10000 or sum(operations.values()) + cost > limit:
            raise ValueError("Organization provider budget exhausted")
        operations[operation] = cost
        period[capability] = operations
        ledger[month] = period
        # Retain three monthly windows, containing only opaque operation hashes
        # and cost bounds. No prompt, media, label or model output is persisted.
        payload["advanced_provider_cost_reservations"] = {key: ledger[key] for key in sorted(ledger)[-3:]}
        query = client.table("organizations").update({"settings": payload}).eq("id", org_id)
        query = query.is_("settings", "null") if raw is None else query.eq("settings", original)
        if query.execute().data:
            return
    raise ValueError("Provider budget changed concurrently; dispatch refused")


def private_artifact_storage(client: Any, settings: Any, org_id: str) -> tuple[str, str]:
    """Check the actual destination, including BYO, before paid generation."""
    from app.services.byo_storage import load_target, org_entitled, s3_client, storage_target_fingerprint
    target = None
    if getattr(settings, "byo_storage_enabled", False) is True and org_entitled(settings, org_id):
        target = load_target(client, org_id)  # Lookup errors fail closed.
        if target and target.get("status") != "verified":
            raise ValueError("Configured organization storage is not verified")
    if target:
        storage = s3_client(settings, target)
        protection = storage.get_public_access_block(Bucket=target["bucket"])["PublicAccessBlockConfiguration"]
        if not all(protection.get(flag) is True for flag in
                   ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")):
            raise ValueError("Generated assets require private organization storage")
        return "byo", storage_target_fingerprint(target)
    bucket = settings.chat_artifacts_bucket
    info = client.storage.get_bucket(bucket)
    public = info.get("public") if isinstance(info, dict) else getattr(info, "public", None)
    if public is not False:
        raise ValueError("Private artifact bucket required")
    return "supabase", bucket
