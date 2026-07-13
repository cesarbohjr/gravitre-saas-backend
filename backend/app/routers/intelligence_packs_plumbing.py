"""Intelligence pack plumbing + Phase 3 invoke_tool smoke routes."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import require_admin
from app.config import Settings, get_settings
from app.intelligence_packs.executive.sources import fetch_fred_series, fetch_world_bank_indicator
from app.intelligence_packs.msp import fetch_nvd_cve
from app.intelligence_packs.shared.pipeline import ensure_plumbing_registered, run_shared_ingestion
from app.services.tool_service import invoke_tool, list_registered_actions
from app.services.tool_types import ToolContext

router = APIRouter(prefix="/api/intelligence-packs", tags=["intelligence-packs-plumbing"])


class PlumbingSmokeBody(BaseModel):
    vendors: list[str] = Field(
        default_factory=lambda: ["fred", "nvd", "world_bank"],
        description="Vendors to exercise through the shared pipeline",
    )
    fred_series_id: str = "GDP"
    nvd_cve_id: str = "CVE-2024-21762"
    world_bank_country: str = "US"
    world_bank_indicator: str = "NY.GDP.MKTP.CD"


class Phase3InvokeSmokeBody(BaseModel):
    fred_series_id: str = "GDP"
    nvd_cve_id: str = "CVE-2024-21762"


@router.post("/plumbing/smoke")
async def intelligence_packs_plumbing_smoke(
    body: PlumbingSmokeBody,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Live evidence path for Phase 1.5 Gates C/D — not chat/agent tool invoke."""
    ensure_plumbing_registered()
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    requested = [str(v).strip().lower() for v in (body.vendors or []) if str(v).strip()]
    if not requested:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="vendors required")

    results: dict[str, Any] = {}
    for vendor in requested:
        if vendor == "fred":
            raw = await fetch_fred_series(body.fred_series_id, settings=settings)
            cache_key = f"series:{body.fred_series_id.strip() or 'GDP'}"
            ttl = 3600
        elif vendor == "nvd":
            raw = await fetch_nvd_cve(body.nvd_cve_id, settings=settings)
            cache_key = f"cve:{(body.nvd_cve_id or '').strip().upper()}"
            ttl = 3600
        elif vendor == "world_bank":
            raw = await fetch_world_bank_indicator(
                body.world_bank_country,
                body.world_bank_indicator,
                settings=settings,
            )
            cache_key = f"indicator:{body.world_bank_country}:{body.world_bank_indicator}"
            ttl = 86400
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported smoke vendor: {vendor}",
            )

        results[vendor] = run_shared_ingestion(
            client,
            org_id=org_id,
            vendor=vendor,
            cache_key=cache_key,
            raw=raw,
            ttl_seconds=ttl,
        )

    all_ok = all(bool(results[v].get("ok")) for v in requested)
    return {
        "pass": all_ok,
        "orgId": org_id,
        "vendors": requested,
        "results": results,
        "agent_tool_router_wiring": "phase_3_available",
        "crm_outcome_emit": "flagged_phase_5_precondition_gap",
        "third_source": "world_bank",
        "note": "Phase 1.5 plumbing smoke — shared surfaces only.",
    }


@router.post("/tools/invoke-smoke")
async def intelligence_packs_phase3_invoke_smoke(
    body: Phase3InvokeSmokeBody,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Phase 3: prove fred.series.get + nvd.cve.get via invoke_tool on the deployed tip."""
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    registered = set(list_registered_actions())
    missing = [a for a in ("fred.series.get", "nvd.cve.get") if a not in registered]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Actions not registered on this tip: {missing}",
        )

    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=org_id,
        actor_id=str(user.get("user_id") or ""),
        environment_name="production",
    )
    results: dict[str, Any] = {}
    for action, params in (
        ("fred.series.get", {"series_id": body.fred_series_id}),
        ("nvd.cve.get", {"cve_id": body.nvd_cve_id}),
    ):
        result = invoke_tool(ctx, action, params)
        ingestion = (result.data or {}).get("ingestion") or {}
        results[action] = {
            "success": result.success,
            "error_code": result.error_code,
            "error_message": result.error_message,
            "cache_id": (ingestion.get("cache") or {}).get("id"),
            "entity_ids": [e.get("id") for e in (ingestion.get("entities") or [])],
            "signal_ids": [s.get("id") for s in (ingestion.get("signals") or [])],
            "shared_surfaces": ingestion.get("shared_surfaces"),
        }

    per_ok = {
        a: bool(results[a]["success"])
        and bool(results[a]["cache_id"])
        and bool(results[a]["entity_ids"])
        and bool(results[a]["signal_ids"])
        for a in results
    }
    return {
        "pass": all(per_ok.values()),
        "orgId": org_id,
        "registered": sorted(a for a in registered if a.startswith(("fred.", "nvd."))),
        "per_action_ok": per_ok,
        "results": results,
        "agent_tool_router_wiring": "phase_3_invoke_tool",
        "note": "Phase 3 invoke_tool smoke on deployed tip — same path ReAct/chat uses.",
    }
