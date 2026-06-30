"""Admin API for org/pack feedback mode toggle and Mode B guardrails (STA-293)."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.feedback_mode_constants import DEFAULT_PACK_SLUG, FEEDBACK_MODE_A, FEEDBACK_MODE_B
from app.services.mode_b_feedback_service import (
    ModeBCapExceededError,
    ModeBFeedbackError,
    ModeBNotEnabledError,
    get_mode_b_feedback_service,
)

router = APIRouter(prefix="/api/admin/feedback-mode", tags=["feedback-mode-admin"])


class SetFeedbackModeRequest(BaseModel):
    feedback_mode: Literal["mode_a", "mode_b"] = FEEDBACK_MODE_A
    pack_slug: str = Field(default=DEFAULT_PACK_SLUG)
    risk_acknowledged: bool = False


class RunReplanCycleRequest(BaseModel):
    pack_slug: str = Field(default=DEFAULT_PACK_SLUG)


@router.get("")
async def get_feedback_mode_settings(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    pack_slug: str = Query(default=DEFAULT_PACK_SLUG),
) -> dict[str, Any]:
    service = get_mode_b_feedback_service(settings)
    return await service.get_feedback_settings(org_id, pack_slug=pack_slug)


@router.put("")
async def set_feedback_mode_settings(
    body: SetFeedbackModeRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user, _org = admin
    user_id = str(user.get("user_id") or user.get("id") or "")
    service = get_mode_b_feedback_service(settings)
    try:
        return await service.set_feedback_mode(
            org_id,
            feedback_mode=body.feedback_mode,
            pack_slug=body.pack_slug,
            actor_id=user_id or None,
            risk_acknowledged=body.risk_acknowledged or body.feedback_mode == FEEDBACK_MODE_A,
        )
    except ModeBFeedbackError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.get("/events")
async def list_mode_b_autonomous_events(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    service = get_mode_b_feedback_service(settings)
    events = await service.list_autonomous_events(org_id, limit=limit)
    return {"events": events}


@router.post("/replan-cycle")
async def run_mode_b_replanning_cycle(
    body: RunReplanCycleRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    service = get_mode_b_feedback_service(settings)
    try:
        return await service.run_replanning_cycle(org_id, pack_slug=body.pack_slug)
    except ModeBNotEnabledError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ModeBCapExceededError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ModeBFeedbackError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/mutations/{mutation_id}/rollback")
async def rollback_mode_b_mutation(
    mutation_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user, _org = admin
    user_id = str(user.get("user_id") or user.get("id") or "")
    service = get_mode_b_feedback_service(settings)
    try:
        return await service.rollback_mutation(org_id, mutation_id, actor_id=user_id or None)
    except ModeBFeedbackError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
