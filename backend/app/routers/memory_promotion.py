"""Admin API for memory promotion (v4) — no UI this session, API-complete for fast-follow."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.memory_promotion_service import get_memory_promotion_service

router = APIRouter(prefix="/api/admin/memory-promotion", tags=["memory-promotion-admin"])


class RejectCandidateRequest(BaseModel):
    reason: str | None = None


class RollbackMemoryRequest(BaseModel):
    reason: str = Field(..., min_length=1)


@router.get("/candidates")
async def list_promotion_candidates(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    service = get_memory_promotion_service(settings)
    return service.list_candidates(org_id, status=status, source=source, limit=limit, offset=offset)


@router.post("/candidates/{candidate_id}/approve")
async def approve_promotion_candidate(
    candidate_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user, _org = admin
    user_id = str(user.get("user_id") or user.get("id") or "")
    service = get_memory_promotion_service(settings)
    try:
        return await service.approve_candidate(candidate_id, org_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/candidates/{candidate_id}/reject")
async def reject_promotion_candidate(
    candidate_id: str,
    body: RejectCandidateRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    user, _org = admin
    user_id = str(user.get("user_id") or user.get("id") or "")
    service = get_memory_promotion_service(settings)
    try:
        await service.reject_candidate(candidate_id, org_id, user_id, body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "rejected"}


@router.post("/memories/{memory_id}/rollback")
async def rollback_promoted_memory(
    memory_id: str,
    body: RollbackMemoryRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    user, _org = admin
    user_id = str(user.get("user_id") or user.get("id") or "")
    service = get_memory_promotion_service(settings)
    try:
        await service.rollback_memory(memory_id, org_id, user_id, body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "rolled_back"}


@router.get("/audit")
async def list_promotion_audit(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    memory_id: str | None = Query(default=None),
    since: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    since_dt = None
    if since:
        try:
            if since.endswith("h") and since[:-1].isdigit():
                since_dt = datetime.now(timezone.utc) - timedelta(hours=int(since[:-1]))
            else:
                since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid since parameter")
    service = get_memory_promotion_service(settings)
    return service.list_audit(org_id, memory_id=memory_id, since=since_dt, limit=limit, offset=offset)


@router.get("/recent-auto-promotions")
async def list_recent_auto_promotions(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    since: str = Query(default="24h"),
    limit: int = Query(default=50, ge=1, le=200),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    hours = 24
    if since.endswith("h") and since[:-1].isdigit():
        hours = int(since[:-1])
    service = get_memory_promotion_service(settings)
    return service.list_recent_auto_promotions(org_id, since_hours=hours, limit=limit)
