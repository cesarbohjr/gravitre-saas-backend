"""Admin endpoints for Gravitre AI architecture layer."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.ai_architecture_status_service import get_ai_architecture_status_service
from app.services.optimization_suggestion_service import get_optimization_suggestion_service

router = APIRouter(prefix="/api/admin", tags=["ai-architecture-admin"])


@router.get("/ai-architecture/registry")
async def get_ai_architecture_registry(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await get_ai_architecture_status_service(settings).get_registry_with_runtime(org_id)


@router.get("/ai-os/status")
async def get_ai_os_status(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await get_ai_architecture_status_service(settings).get_ai_os_status(org_id)


@router.get("/learning/status")
async def get_continuous_learning_status(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await get_ai_architecture_status_service(settings).get_learning_status(org_id)


@router.get("/intelligence/predictive-ops")
async def get_predictive_ops(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await get_ai_architecture_status_service(settings).get_predictive_ops_status(org_id)


@router.get("/optimization/summary")
async def get_optimization_summary(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    service = get_optimization_suggestion_service(settings)
    return await service.get_summary(org_id)
