"""WorkObject API.

Durable business lifecycle objects that aggregate multiple BusinessOutcomes.
"""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.services.work_object_service import (
    get_work_object,
    list_work_object_events,
    list_work_objects,
    summarize_work_object_coverage,
)
from app.workflows.repository import get_supabase_client

router = APIRouter(prefix="/api/work-objects", tags=["work-objects"])


@router.get("")
async def list_work_objects_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    object_type: str | None = Query(default=None, alias="objectType"),
    department: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    items = list_work_objects(
        client,
        org_id=org_id,
        object_type=object_type,
        department=department,
        status=status_filter,
        priority=priority,
        limit=limit,
    )
    return {"workObjects": items, "count": len(items)}


@router.get("/coverage")
async def work_object_coverage_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    coverage = summarize_work_object_coverage(client, org_id=org_id)
    return {"coverage": coverage}


@router.get("/{work_object_id}")
async def get_work_object_route(
    work_object_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    events_limit: int = Query(default=150, ge=1, le=500, alias="eventsLimit"),
) -> dict[str, Any]:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    item = get_work_object(client, org_id=org_id, work_object_id=str(work_object_id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WorkObject not found")
    events = list_work_object_events(
        client,
        org_id=org_id,
        work_object_id=str(work_object_id),
        limit=events_limit,
    )
    return {"workObject": item, "events": events}
