"""Admin API for v10 optimization suggestions (human-gated only)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.optimization_suggestion_service import get_optimization_suggestion_service

router = APIRouter(prefix="/api/admin/optimization-suggestions", tags=["optimization-suggestions-admin"])


class DismissSuggestionRequest(BaseModel):
    reason: str | None = None


class MarkAppliedRequest(BaseModel):
    applied_change_summary: str = Field(..., min_length=1)


class ApplySuggestionRequest(BaseModel):
    preview_token: str = Field(..., min_length=1)


@router.get("")
async def list_optimization_suggestions(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    service = get_optimization_suggestion_service(settings)
    return await service.list_suggestions(
        org_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.post("/detect")
async def detect_optimization_suggestions(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    service = get_optimization_suggestion_service(settings)
    suggestions = await service.detect_suggestions_for_org(org_id)
    return {"detected": len(suggestions), "suggestions": suggestions}


@router.post("/{suggestion_id}/dismiss")
async def dismiss_optimization_suggestion(
    suggestion_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    body: DismissSuggestionRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user, _org = admin
    user_id = str(user.get("user_id") or user.get("id") or "")
    service = get_optimization_suggestion_service(settings)
    try:
        return await service.dismiss_suggestion(
            org_id,
            suggestion_id,
            reviewed_by=user_id or None,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{suggestion_id}/apply-preview")
async def preview_optimization_suggestion_apply(
    suggestion_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    service = get_optimization_suggestion_service(settings)
    try:
        return await service.generate_apply_preview(org_id, suggestion_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{suggestion_id}/apply")
async def apply_optimization_suggestion(
    suggestion_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    body: ApplySuggestionRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user, _org = admin
    user_id = str(user.get("user_id") or user.get("id") or "")
    service = get_optimization_suggestion_service(settings)
    try:
        return await service.apply_suggestion(
            org_id,
            suggestion_id,
            preview_token=body.preview_token,
            reviewed_by=user_id or None,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_400_BAD_REQUEST
        if "not found" in detail.lower():
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post("/{suggestion_id}/mark-applied")
async def mark_optimization_suggestion_applied(
    suggestion_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    body: MarkAppliedRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user, _org = admin
    user_id = str(user.get("user_id") or user.get("id") or "")
    service = get_optimization_suggestion_service(settings)
    try:
        return await service.mark_applied(
            org_id,
            suggestion_id,
            reviewed_by=user_id or None,
            applied_change_summary=body.applied_change_summary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
