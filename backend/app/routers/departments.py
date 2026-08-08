"""Department assignment + department-manager scoped APIs (Phase 2 / D1)."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.billing.seat_context import (
    assert_department_manager,
    list_assigned_resource_ids,
    resolve_seat_context,
    response_error,
)
from app.config import Settings, get_settings
from app.core.errors import error_detail

router = APIRouter(prefix="/api/departments", tags=["departments"])

ResourceType = Literal["workflow", "agent", "council"]


class AssignResourceRequest(BaseModel):
    department_id: str = Field(..., min_length=1)
    resource_type: ResourceType
    resource_id: str = Field(..., min_length=1)


def _client(settings: Settings):
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _seat(
    current_user: dict,
    org_id: str,
    settings: Settings,
) -> dict[str, Any]:
    return resolve_seat_context(
        _client(settings),
        org_id=org_id,
        user_id=str(current_user.get("user_id") or ""),
    )


@router.get("/me")
async def get_my_department_scope(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    seat = _seat(current_user, org_id, settings)
    return {
        "is_lite": seat["is_lite"],
        "is_full_seat": seat["is_full_seat"],
        "is_org_admin": seat["is_org_admin"],
        "is_department_manager": bool(seat.get("managed_department_ids")) or seat["is_org_admin"],
        "departments": seat["departments"],
        "managed_department_ids": seat["managed_department_ids"],
        "member_department_ids": seat["member_department_ids"],
    }


@router.get("/{department_id}/assignments")
async def list_department_assignments(
    department_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    resource_type: ResourceType | None = Query(default=None),
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    seat = _seat(current_user, org_id, settings)
    # Lite members can read their own department assignments; managers/admins can manage.
    member_ids = set(seat.get("member_department_ids") or [])
    if not seat["is_org_admin"] and department_id not in member_ids and department_id not in set(
        seat.get("managed_department_ids") or []
    ):
        raise HTTPException(
            status_code=403,
            detail=error_detail("Outside department scope", "UNAUTHORIZED"),
        )
    client = _client(settings)
    q = (
        client.table("department_resource_assignments")
        .select("id, department_id, resource_type, resource_id, assigned_by, created_at")
        .eq("org_id", org_id)
        .eq("department_id", department_id)
    )
    if resource_type:
        q = q.eq("resource_type", resource_type)
    resp = q.execute()
    err = response_error(resp)
    if err:
        # Table may not be migrated yet — fail soft with empty list.
        if "department_resource_assignments" in str(err):
            return {"assignments": []}
        raise HTTPException(status_code=500, detail=str(err))
    return {"assignments": list(resp.data or [])}


@router.post("/assignments")
async def assign_department_resource(
    body: AssignResourceRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    seat = _seat(current_user, org_id, settings)
    assert_department_manager(seat, body.department_id)
    client = _client(settings)
    # Ensure department belongs to org.
    dept = (
        client.table("departments")
        .select("id, org_id")
        .eq("id", body.department_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not dept.data:
        raise HTTPException(status_code=404, detail="Department not found")
    row = {
        "org_id": org_id,
        "department_id": body.department_id,
        "resource_type": body.resource_type,
        "resource_id": body.resource_id.strip(),
        "assigned_by": current_user.get("user_id"),
    }
    try:
        resp = (
            client.table("department_resource_assignments")
            .upsert(row, on_conflict="department_id,resource_type,resource_id")
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=error_detail(str(exc), "INTERNAL_ERROR", {"hint": "apply department_resource_assignments migration"}),
        ) from exc
    err = response_error(resp)
    if err:
        raise HTTPException(status_code=500, detail=str(err))
    return {"assignment": (resp.data or [row])[0]}


@router.delete("/assignments")
async def unassign_department_resource(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    department_id: str = Query(...),
    resource_type: ResourceType = Query(...),
    resource_id: str = Query(...),
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    seat = _seat(current_user, org_id, settings)
    assert_department_manager(seat, department_id)
    client = _client(settings)
    try:
        client.table("department_resource_assignments").delete().eq("org_id", org_id).eq(
            "department_id", department_id
        ).eq("resource_type", resource_type).eq("resource_id", resource_id).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/assigned/{resource_type}")
async def list_my_assigned_resources(
    resource_type: ResourceType,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Lite + managers: resources assigned to their departments."""
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    seat = _seat(current_user, org_id, settings)
    if seat["is_org_admin"]:
        # Org admins see all assignments in the org.
        client = _client(settings)
        try:
            resp = (
                client.table("department_resource_assignments")
                .select("resource_id, department_id, resource_type")
                .eq("org_id", org_id)
                .eq("resource_type", resource_type)
                .execute()
            )
            ids = sorted({str(r.get("resource_id")) for r in (resp.data or []) if r.get("resource_id")})
        except Exception:
            ids = []
        return {"resource_type": resource_type, "resource_ids": ids, "scope": "org"}
    dept_ids = list(seat.get("member_department_ids") or [])
    ids = sorted(
        list_assigned_resource_ids(
            _client(settings),
            org_id=org_id,
            department_ids=dept_ids,
            resource_type=resource_type,
        )
    )
    return {
        "resource_type": resource_type,
        "resource_ids": ids,
        "scope": "department",
        "department_ids": dept_ids,
    }


# Keep require_admin import used for future org-admin-only department CRUD expansion.
_ = require_admin
