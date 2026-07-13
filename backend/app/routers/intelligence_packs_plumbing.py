"""Phase 1.5 live smoke — dedicated HTTP path (NOT agent/tool/router chat).

POST /api/intelligence-packs/plumbing/smoke
Exercises shared cache → normalize → KG write → PackSignalDefinition for
fred / nvd / world_bank. Agent chat wiring is deferred to Phase 3.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.config import Settings, get_settings
from app.deps import require_admin
from app.intelligence_packs.executive.sources import fetch_fred_series, fetch_world_bank_indicator
from app.intelligence_packs.msp import fetch_nvd_cve
from app.intelligence_packs.shared.pipeline import ensure_plumbing_registered, run_shared_ingestion

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

        # If fetch unavailable (missing keys), still allow dry normalize of synthetic ok
        # only when ok — otherwise record failure honestly for that vendor.
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
        "agent_tool_router_wiring": "deferred_to_phase_3",
        "crm_outcome_emit": "flagged_phase_5_precondition_gap",
        "third_source": "world_bank",
        "note": "Phase 1.5 plumbing smoke — shared surfaces only; not agent chat.",
    }
