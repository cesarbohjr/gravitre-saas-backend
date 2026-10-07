"""Business metrics and dashboard templates, backed only by verified Play results.

Definitions come from the canonical metric catalog (Outcome Packs plus org
overrides). Values come only from source-of-record VERIFIED SUCCESS rows on the
Play outcome ledger; no evidence is reported as unknown, never as zero.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import require_org_member
from app.config import Settings, get_settings
from app.services.business_metrics_service import (
    business_metric_catalog,
    business_metric_evidence,
    compute_business_metrics,
)
from app.workflows.repository import get_supabase_client

router = APIRouter(tags=["business-metrics"])

RangeParam = Annotated[str, Query(pattern="^(7d|30d|90d|365d|all)$")]


def _org(member: tuple[dict, str, str]) -> str:
    _user, org_id, _role = member
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    return str(org_id)


@router.get("/api/metrics/business/catalog")
async def get_business_metric_catalog(
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    return business_metric_catalog(get_supabase_client(settings), _org(member))


@router.get("/api/metrics/business")
async def get_business_metrics(
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
    range: RangeParam = "30d",
    metric_keys: Annotated[str | None, Query(max_length=2000)] = None,
) -> dict[str, Any]:
    keys = [k for k in (metric_keys or "").split(",") if k.strip()] or None
    return compute_business_metrics(
        get_supabase_client(settings), _org(member), range_key=range, metric_keys=keys
    )


@router.get("/api/metrics/business/{metric_key}/evidence")
async def get_business_metric_evidence(
    metric_key: str,
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
    range: RangeParam = "30d",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict[str, Any]:
    return business_metric_evidence(
        get_supabase_client(settings), _org(member), metric_key, range_key=range, limit=limit
    )


def _installed_dashboard_packs(client: Any, org_id: str) -> list[dict[str, Any]]:
    try:
        rows = (
            client.table("marketplace_dashboard_pack_installations")
            .select("id, asset_id, source_outcome_pack_id, status, config, created_at")
            .eq("org_id", org_id)
            .eq("status", "active")
            .limit(200)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001 - table may be absent in older environments
        return []
    out = []
    for row in rows:
        config = row.get("config") if isinstance(row.get("config"), dict) else {}
        out.append(
            {
                "installationId": row.get("id"),
                "assetId": row.get("asset_id"),
                "templateId": config.get("template_id"),
                "title": config.get("title"),
                "department": config.get("department"),
                "installedAt": row.get("created_at"),
            }
        )
    return out


@router.get("/api/dashboard-templates")
async def list_dashboard_templates(
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    from app.outcome_packs.registry import dashboard_templates

    installed = {
        str(p.get("templateId"))
        for p in _installed_dashboard_packs(get_supabase_client(settings), _org(member))
        if p.get("templateId")
    }
    return {
        "templates": [
            {**template, "installed": template["templateId"] in installed}
            for template in dashboard_templates()
        ]
    }


@router.get("/api/marketplace/dashboard-packs/installed")
async def list_installed_dashboard_packs(
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    return {"dashboardPacks": _installed_dashboard_packs(get_supabase_client(settings), _org(member))}
