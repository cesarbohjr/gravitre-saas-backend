"""Unified schedules dashboard API."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.config import Settings, get_settings
from app.services.schedules_aggregation_service import (
    default_projection_window,
    list_scheduled_items,
    parse_iso_datetime,
    parse_kinds_param,
)
from app.workflows.repository import get_supabase_client

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("")
async def list_schedules(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    workflow_id: str | None = Query(default=None, alias="workflow_id"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    kinds: str | None = Query(default=None),
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")

    try:
        selected_kinds = parse_kinds_param(kinds)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    window_start, window_end = default_projection_window()
    parsed_from = parse_iso_datetime(from_)
    parsed_to = parse_iso_datetime(to)
    if from_ and parsed_from is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid from timestamp")
    if to and parsed_to is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid to timestamp")
    if parsed_from:
        window_start = parsed_from
    if parsed_to:
        window_end = parsed_to
    if window_end <= window_start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="to must be after from")

    client = get_supabase_client(settings)
    items = list_scheduled_items(
        client,
        org_id,
        environment_name,
        workflow_id=(workflow_id or "").strip() or None,
        window_start=window_start,
        window_end=window_end,
        kinds=selected_kinds,
    )
    return {"items": items}
