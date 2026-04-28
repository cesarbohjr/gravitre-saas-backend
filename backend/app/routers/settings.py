"""Phase 15: Settings API."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdateRequest(BaseModel):
    settings: dict


class LiteSeatCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    lite_seat_allocation: int = Field(..., ge=0)
    department_admin_id: str | None = None


class LiteSeatUpdateRequest(BaseModel):
    id: str
    name: str | None = None
    lite_seat_allocation: int | None = Field(default=None, ge=0)
    department_admin_id: str | None = None


class MesonAddonUpdateRequest(BaseModel):
    code: str
    enabled: bool


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    return "does not exist" in str(error).lower()


def _current_month_start_iso() -> str:
    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    return month_start.isoformat()


def _included_outputs_for_tier(tier: str) -> int | None:
    mapping: dict[str, int | None] = {
        "free": 200,
        "node": 1000,
        "control": 10000,
        "command": None,
    }
    return mapping.get((tier or "free").strip().lower(), 200)


@router.get("")
async def get_settings_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    r = client.table("organizations").select("id, settings").eq("id", org_id).limit(1).execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"settings": r.data[0].get("settings") or {}}


@router.patch("")
async def update_settings_route(
    body: SettingsUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    updated = client.table("organizations").update({"settings": body.settings}).eq("id", org_id).execute()
    if not updated.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="settings.updated",
        resource_type="org_settings",
        resource_id=str(org_id),
        metadata={},
    )
    return {"settings": body.settings}


@router.get("/lite-seats")
async def get_lite_seats_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    departments_resp = (
        client.table("departments")
        .select("id, org_id, name, lite_seat_allocation, department_admin_id, created_at")
        .eq("org_id", org_id)
        .order("created_at", desc=False)
        .execute()
    )
    if _is_missing_table_error(departments_resp.error):
        return {"summary": {"included": 0, "allocated": 0, "used": 0}, "departments": []}
    if departments_resp.error:
        raise HTTPException(status_code=500, detail=str(departments_resp.error))
    departments = list(departments_resp.data or [])

    members_resp = (
        client.table("department_members")
        .select("id, department_id")
        .in_("department_id", [d["id"] for d in departments] or ["00000000-0000-0000-0000-000000000000"])
        .execute()
    )
    members_by_department: dict[str, int] = defaultdict(int)
    if not _is_missing_table_error(members_resp.error):
        for member in members_resp.data or []:
            dept_id = member.get("department_id")
            if dept_id:
                members_by_department[str(dept_id)] += 1

    subscription_resp = (
        client.table("subscriptions")
        .select("lite_seats")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    included = 0
    if not _is_missing_table_error(subscription_resp.error):
        included = int((subscription_resp.data or [{}])[0].get("lite_seats") or 0)

    allocated = sum(int(d.get("lite_seat_allocation") or 0) for d in departments)
    used = sum(members_by_department.values())
    result = []
    for d in departments:
        dept_id = str(d["id"])
        allocation = int(d.get("lite_seat_allocation") or 0)
        used_seats = int(members_by_department.get(dept_id, 0))
        result.append(
            {
                "id": dept_id,
                "name": d.get("name") or "",
                "lite_seat_allocation": allocation,
                "used_seats": used_seats,
                "available_seats": max(allocation - used_seats, 0),
                "department_admin_id": d.get("department_admin_id"),
                "status": "active" if allocation > 0 else "inactive",
                "created_at": d.get("created_at"),
            }
        )

    return {"summary": {"included": included, "allocated": allocated, "used": used}, "departments": result}


@router.post("/lite-seats")
async def create_lite_seat_department_route(
    body: LiteSeatCreateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    created = (
        client.table("departments")
        .insert(
            {
                "org_id": org_id,
                "name": body.name.strip(),
                "lite_seat_allocation": body.lite_seat_allocation,
                "department_admin_id": body.department_admin_id,
            }
        )
        .select("id, org_id, name, lite_seat_allocation, department_admin_id, created_at")
        .single()
        .execute()
    )
    if created.error:
        raise HTTPException(status_code=500, detail=str(created.error))
    return {"department": created.data}


@router.patch("/lite-seats")
async def update_lite_seat_department_route(
    body: LiteSeatUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    payload: dict = {}
    if body.name is not None:
        payload["name"] = body.name.strip()
    if body.lite_seat_allocation is not None:
        payload["lite_seat_allocation"] = body.lite_seat_allocation
    if body.department_admin_id is not None:
        payload["department_admin_id"] = body.department_admin_id
    if not payload:
        raise HTTPException(status_code=400, detail="No updates provided")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    updated = (
        client.table("departments")
        .update(payload)
        .eq("org_id", org_id)
        .eq("id", body.id)
        .select("id, org_id, name, lite_seat_allocation, department_admin_id, created_at")
        .single()
        .execute()
    )
    if updated.error:
        raise HTTPException(status_code=500, detail=str(updated.error))
    return {"department": updated.data}


@router.delete("/lite-seats")
async def delete_lite_seat_department_route(
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    department_id: str = Query(..., alias="departmentId"),
) -> dict:
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    deleted = (
        client.table("departments")
        .delete()
        .eq("org_id", org_id)
        .eq("id", department_id)
        .execute()
    )
    if deleted.error:
        raise HTTPException(status_code=500, detail=str(deleted.error))
    return {"success": True}


@router.get("/meson-addons")
async def get_meson_addons_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    catalog_resp = (
        client.table("meson_addon_catalog")
        .select("id, code, name, description, monthly_price_usd")
        .order("monthly_price_usd", desc=False)
        .execute()
    )
    if _is_missing_table_error(catalog_resp.error):
        return {"addons": [], "monthly_total_usd": 0}
    if catalog_resp.error:
        raise HTTPException(status_code=500, detail=str(catalog_resp.error))

    sub_resp = (
        client.table("subscriptions")
        .select("meson_addons")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    enabled_codes: set[str] = set()
    if not _is_missing_table_error(sub_resp.error):
        values = (sub_resp.data or [{}])[0].get("meson_addons") or []
        if isinstance(values, list):
            enabled_codes = {str(item) for item in values}

    addons = []
    monthly_total = 0.0
    for row in catalog_resp.data or []:
        code = str(row.get("code") or "")
        monthly_price = float(row.get("monthly_price_usd") or 0)
        enabled = code in enabled_codes
        if enabled:
            monthly_total += monthly_price
        addons.append(
            {
                "id": row.get("id"),
                "code": code,
                "name": row.get("name") or "",
                "description": row.get("description") or "",
                "monthly_price_usd": monthly_price,
                "enabled": enabled,
            }
        )
    return {"addons": addons, "monthly_total_usd": monthly_total}


@router.patch("/meson-addons")
async def update_meson_addons_route(
    body: MesonAddonUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    existing = (
        client.table("subscriptions").select("meson_addons").eq("org_id", org_id).limit(1).execute()
    )
    if _is_missing_table_error(existing.error):
        raise HTTPException(status_code=400, detail="subscriptions table missing; run migrations")
    if existing.error:
        raise HTTPException(status_code=500, detail=str(existing.error))
    current = (existing.data or [{}])[0].get("meson_addons") or []
    if not isinstance(current, list):
        current = []
    enabled = {str(item) for item in current}
    if body.enabled:
        enabled.add(body.code)
    else:
        enabled.discard(body.code)
    updated = (
        client.table("subscriptions")
        .upsert({"org_id": org_id, "meson_addons": sorted(enabled)}, on_conflict="org_id")
        .select("org_id, meson_addons")
        .single()
        .execute()
    )
    if updated.error:
        raise HTTPException(status_code=500, detail=str(updated.error))
    return {"subscription": updated.data}


@router.get("/billing-usage")
async def get_billing_usage_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    month_start = _current_month_start_iso()
    usage_resp = (
        client.table("usage_records")
        .select("metric_type, quantity, recorded_at")
        .eq("org_id", org_id)
        .gte("recorded_at", month_start)
        .execute()
    )
    if _is_missing_table_error(usage_resp.error):
        return {
            "period_start": month_start,
            "totals": {"outputs": 0, "workflow_runs": 0, "api_calls": 0, "ai_tokens": 0},
            "included_outputs": 0,
            "overage_outputs": 0,
            "overage_cost_usd": 0,
        }
    if usage_resp.error:
        raise HTTPException(status_code=500, detail=str(usage_resp.error))

    totals = {"outputs": 0, "workflow_runs": 0, "api_calls": 0, "ai_tokens": 0}
    for row in usage_resp.data or []:
        metric = str(row.get("metric_type") or "")
        quantity = int(row.get("quantity") or 0)
        if metric in totals:
            totals[metric] += quantity

    sub_resp = client.table("subscriptions").select("tier").eq("org_id", org_id).limit(1).execute()
    tier = "free"
    if not _is_missing_table_error(sub_resp.error):
        tier = str((sub_resp.data or [{}])[0].get("tier") or "free")
    included_outputs = _included_outputs_for_tier(tier)
    output_total = totals["outputs"]
    overage_outputs = 0
    if included_outputs is not None:
        overage_outputs = max(output_total - included_outputs, 0)
    overage_cost_usd = round(overage_outputs * 0.01, 2)
    return {
        "period_start": month_start,
        "tier": tier,
        "totals": totals,
        "included_outputs": included_outputs,
        "overage_outputs": overage_outputs,
        "overage_cost_usd": overage_cost_usd,
    }
