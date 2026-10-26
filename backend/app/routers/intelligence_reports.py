"""Intelligence › Reports: saved views shared with the team, and scheduled report email."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import require_org_member
from app.config import Settings, get_settings
from app.services.intelligence_reports_service import (
    CADENCES,
    TEMPLATES,
    TIMES,
    ReportsInputError,
    delete_view,
    get_schedule,
    list_views,
    public_view,
    save_view,
    set_schedule,
)
from app.workflows.repository import get_supabase_client

router = APIRouter(prefix="/api/intelligence/reports", tags=["intelligence-reports"])

_ADMIN_ROLES = frozenset({"owner", "admin"})


class SaveViewRequest(BaseModel):
    templateId: str = Field(..., min_length=1, max_length=32)
    periodDays: int
    label: str | None = Field(default=None, max_length=80)


class ScheduleRequest(BaseModel):
    templateId: str = Field(..., min_length=1, max_length=32)
    periodDays: int = 7
    cadence: str = Field(..., min_length=1, max_length=32)
    time: str = Field(..., min_length=1, max_length=8)
    enabled: bool = True


def _who(member: tuple) -> tuple[str, str, bool, str | None]:
    user, org_id, role = member
    user_id = str(user.get("user_id") or user.get("sub") or "")
    return user_id, org_id, str(role or "").lower() in _ADMIN_ROLES, user.get("email")


def _options(settings: Settings) -> dict[str, Any]:
    return {
        "templates": [{"id": k, "label": v} for k, v in TEMPLATES.items()],
        "cadences": [{"id": k, "label": v} for k, v in CADENCES.items()],
        "times": list(TIMES),
        "emailEnabled": bool(settings.notification_email_enabled),
    }


@router.get("/views")
def reports_list_views(
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user_id, org_id, is_admin, _email = _who(member)
    client = get_supabase_client(settings)
    return {"views": list_views(client, org_id, user_id=user_id, is_admin=is_admin)}


@router.post("/views", status_code=status.HTTP_201_CREATED)
def reports_save_view(
    body: SaveViewRequest,
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user_id, org_id, is_admin, email = _who(member)
    client = get_supabase_client(settings)
    try:
        view = save_view(
            client,
            org_id,
            user_id=user_id,
            user_name=email,
            template_id=body.templateId,
            period_days=body.periodDays,
            label=body.label,
        )
    except ReportsInputError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return {"view": public_view(view, user_id=user_id, is_admin=is_admin)}


@router.delete("/views/{view_id}")
def reports_delete_view(
    view_id: str,
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user_id, org_id, is_admin, _email = _who(member)
    client = get_supabase_client(settings)
    try:
        removed = delete_view(client, org_id, view_id=view_id[:64], user_id=user_id, is_admin=is_admin)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="That saved view no longer exists.")
    return {"removed": True}


@router.get("/schedule")
def reports_get_schedule(
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user_id, org_id, _is_admin, _email = _who(member)
    client = get_supabase_client(settings)
    return {"schedule": get_schedule(client, org_id, user_id=user_id), **_options(settings)}


@router.put("/schedule")
def reports_put_schedule(
    body: ScheduleRequest,
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user_id, org_id, _is_admin, _email = _who(member)
    if body.enabled and not settings.notification_email_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email delivery is turned off for Gravitre right now, so a scheduled report would not arrive.",
        )
    client = get_supabase_client(settings)
    try:
        schedule = set_schedule(
            client,
            org_id,
            user_id=user_id,
            template_id=body.templateId,
            period_days=body.periodDays,
            cadence=body.cadence,
            time=body.time,
            enabled=body.enabled,
        )
    except ReportsInputError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return {"schedule": schedule, **_options(settings)}
