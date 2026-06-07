"""Enterprise platform APIs — Tier 4 compliance, branding, analytics, SIEM (STA-80–95)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.billing.service import get_plan_for_org, require_feature
from app.config import Settings, get_settings
from app.core.errors import error_detail
from app.services.agent_cost_service import aggregate_agent_costs
from app.services.branding_service import get_org_branding, merge_branding
from app.services.compliance_service import build_soc2_evidence_bundle
from app.services.data_residency_service import (
    get_org_data_region,
    normalize_region,
    resolve_execution_region,
    storage_prefix,
)
from app.services.siem_export_service import build_siem_event, dispatch_siem_event
from app.services.workforce_analytics_service import build_workforce_analytics
from app.workers.queue import is_queue_available
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/enterprise", tags=["enterprise"])


class DataRegionUpdate(BaseModel):
    region: str = Field(..., pattern="^(us|eu)$")


class BrandingUpdate(BaseModel):
    logo_url: str | None = Field(default=None, alias="logoUrl")
    primary_color: str | None = Field(default=None, alias="primaryColor")
    custom_domain: str | None = Field(default=None, alias="customDomain")
    hide_powered_by: bool | None = Field(default=None, alias="hidePoweredBy")
    email_from_name: str | None = Field(default=None, alias="emailFromName")


class SiemConfigUpdate(BaseModel):
    endpoint: str
    secret: str
    enabled: bool = True


class SiemTestRequest(BaseModel):
    endpoint: str
    secret: str


def _org_settings(client: Any, org_id: str) -> dict[str, Any]:
    row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    settings = row.data[0].get("settings") or {}
    return settings if isinstance(settings, dict) else {}


def _save_org_settings(client: Any, org_id: str, settings: dict[str, Any]) -> dict[str, Any]:
    updated = client.table("organizations").update({"settings": settings}).eq("id", org_id).execute()
    if not updated.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    return updated.data[0].get("settings") or {}


def _parse_window(from_ts: str | None, to_ts: str | None) -> tuple[str | None, str | None]:
    return from_ts, to_ts


@router.get("/data-region")
async def get_data_region(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _org_settings(client, org_id)
    region = get_org_data_region(org_settings)
    return {"region": region, "storagePrefix": storage_prefix(org_id, region)}


@router.put("/data-region")
async def update_data_region(
    body: DataRegionUpdate,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _org_settings(client, org_id)
    region = normalize_region(body.region)
    enterprise = dict(org_settings.get("enterprise") or {})
    enterprise["dataResidency"] = {"region": region}
    org_settings["enterprise"] = enterprise
    org_settings["data_region"] = region
    saved = _save_org_settings(client, org_id, org_settings)
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="enterprise.data_region.updated",
        resource_type="organization",
        resource_id=org_id,
        metadata={"region": region},
    )
    return {"region": get_org_data_region(saved), "storagePrefix": storage_prefix(org_id, region)}


@router.get("/execution-region")
async def get_execution_region(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    region = resolve_execution_region(_org_settings(client, org_id))
    return {"region": region, "queueAvailable": is_queue_available()}


@router.get("/compliance/soc2-export")
async def export_soc2_bundle(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    from_ts: Annotated[str | None, Query(alias="from")] = None,
    to_ts: Annotated[str | None, Query(alias="to")] = None,
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    require_feature(get_plan_for_org(client, org_id), "audit_logs")
    audit_logs = client.table("audit_logs").select("*").eq("org_id", org_id).execute().data or []
    tool_events = [row for row in audit_logs if str(row.get("action") or "").startswith("tool.invoke")]
    connector_events = [row for row in audit_logs if "connector" in str(row.get("action") or "")]
    admin_events = [row for row in audit_logs if str(row.get("action") or "").startswith(("settings.", "enterprise.", "sso."))]
    return build_soc2_evidence_bundle(
        org_id=org_id,
        audit_logs=audit_logs,
        tool_events=tool_events,
        connector_events=connector_events,
        admin_events=admin_events,
        from_ts=from_ts,
        to_ts=to_ts,
    )


@router.get("/branding")
async def get_branding(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return get_org_branding(_org_settings(client, org_id))


@router.put("/branding")
async def update_branding(
    body: BrandingUpdate,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _org_settings(client, org_id)
    updates = body.model_dump(by_alias=True, exclude_none=True)
    saved = _save_org_settings(client, org_id, merge_branding(org_settings, updates))
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="enterprise.branding.updated",
        resource_type="organization",
        resource_id=org_id,
        metadata={"keys": sorted(updates.keys())},
    )
    return get_org_branding(saved)


@router.get("/workforce-analytics")
async def workforce_analytics(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    jobs = client.table("agent_jobs").select("status,kind,created_at").eq("org_id", org_id).execute().data or []
    audit_logs = client.table("audit_logs").select("action,details,created_at").eq("org_id", org_id).execute().data or []
    handoffs = [row for row in audit_logs if "handoff" in str(row.get("action") or "")]
    return build_workforce_analytics(agent_jobs=jobs, audit_logs=audit_logs, handoff_events=handoffs)


@router.get("/cost-attribution")
async def cost_attribution(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usage = (
        client.table("usage_events")
        .select("category,cost_usd,amount_usd,metadata,created_at")
        .eq("org_id", org_id)
        .gte("created_at", month_start.isoformat())
        .execute()
        .data
        or []
    )
    return aggregate_agent_costs(usage_rows=usage)


@router.get("/siem")
async def get_siem_config(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _org_settings(client, org_id)
    enterprise = org_settings.get("enterprise") if isinstance(org_settings.get("enterprise"), dict) else {}
    siem = enterprise.get("siem") if isinstance(enterprise.get("siem"), dict) else {}
    return {
        "enabled": bool(siem.get("enabled")),
        "endpoint": siem.get("endpoint"),
        "hasSecret": bool(siem.get("secret")),
    }


@router.put("/siem")
async def update_siem_config(
    body: SiemConfigUpdate,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_settings = _org_settings(client, org_id)
    enterprise = dict(org_settings.get("enterprise") or {})
    enterprise["siem"] = {
        "enabled": body.enabled,
        "endpoint": body.endpoint.strip(),
        "secret": body.secret.strip(),
    }
    org_settings["enterprise"] = enterprise
    _save_org_settings(client, org_id, org_settings)
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="enterprise.siem.updated",
        resource_type="organization",
        resource_id=org_id,
        metadata={"enabled": body.enabled},
    )
    return {"enabled": body.enabled, "endpoint": body.endpoint.strip(), "hasSecret": True}


@router.post("/siem/test")
async def test_siem_delivery(
    body: SiemTestRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _user, org_id = admin
    event = build_siem_event(
        org_id=org_id,
        action="enterprise.siem.test",
        resource_type="organization",
        resource_id=org_id,
        metadata={"actorId": _user["user_id"]},
    )
    return dispatch_siem_event(endpoint=body.endpoint.strip(), secret=body.secret.strip(), event=event)
