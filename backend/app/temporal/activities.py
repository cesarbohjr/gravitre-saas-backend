"""Temporal activities — thin wrappers around existing service functions."""
from __future__ import annotations

import asyncio
from typing import Any

from temporalio import activity

from app.config import get_settings


@activity.defn
async def run_company_intelligence_for_org(org_id: str) -> dict[str, Any]:
    from app.services.company_intelligence_orchestrator import run_company_intelligence_for_org_sync

    settings = get_settings()
    return await asyncio.to_thread(run_company_intelligence_for_org_sync, org_id, settings)


@activity.defn
async def run_memory_promotion_evaluation(org_id: str) -> dict[str, Any]:
    from app.services.memory_promotion_service import get_memory_promotion_service

    settings = get_settings()
    service = get_memory_promotion_service(settings)
    return await service.run_evaluation(org_id)


@activity.defn
async def load_outcome_baseline(outcome_id: str) -> dict[str, Any]:
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    rows = (
        client.table("agent_action_outcomes")
        .select("*")
        .eq("id", outcome_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise ValueError(f"Outcome not found: {outcome_id}")
    row = rows[0]
    return {
        "outcome_id": outcome_id,
        "org_id": str(row.get("org_id") or ""),
        "attribution_window_days": int(row.get("attribution_window_days") or 14),
    }


@activity.defn
async def measure_outcome_after_window(outcome_id: str) -> dict[str, Any]:
    from app.services.outcome_attribution_service import get_outcome_attribution_service

    settings = get_settings()
    service = get_outcome_attribution_service(settings)
    client = service._client()
    rows = (
        client.table("agent_action_outcomes")
        .select("*")
        .eq("id", outcome_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return {"measured": False, "reason": "not_found"}
    row = rows[0]
    org_id = str(row.get("org_id") or "")
    measured = await service.measure_outcomes_due(org_id)
    return {"measured": measured > 0, "outcome_id": outcome_id}


@activity.defn
async def train_ml_model_for_org(org_id: str, model_name: str) -> dict[str, Any]:
    from app.ml.model_catalog import train_ml_model_for_org as run_training

    settings = get_settings()
    return await run_training(org_id, model_name, settings=settings)


@activity.defn
async def install_marketplace_asset_step(payload: dict[str, Any]) -> dict[str, Any]:
    """Single install step; workflow checkpoints between asset entity installs."""
    from app.marketplace.service import install_asset
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    result = install_asset(
        client,
        str(payload["org_id"]),
        str(payload["asset_id"]),
        actor_id=str(payload.get("actor_id") or "system"),
        environment_name=str(payload.get("environment_name") or "production"),
        install_variables=payload.get("install_variables"),
        force=bool(payload.get("force", False)),
    )
    return {"asset_id": payload["asset_id"], "result": result}


@activity.defn
async def install_marketplace_asset(payload: dict[str, Any]) -> dict[str, Any]:
    return await install_marketplace_asset_step(payload)
