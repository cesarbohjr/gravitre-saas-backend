"""Admin ML catalog API."""
from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import asyncio

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.ml.model_catalog import (
    build_ml_catalog_dashboard,
    get_org_model_status,
    train_ml_model_for_org,
    require_supported_manual_training,
)
from app.temporal.starters import start_ml_model_training_workflow

router = APIRouter(prefix="/api/admin/ml", tags=["ml-admin"])


@router.get("/models")
async def list_ml_catalog(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await build_ml_catalog_dashboard(org_id, settings=settings, include_advanced=True)


@router.get("/models/{model_name}/status")
async def get_ml_model_status(
    model_name: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        return await get_org_model_status(org_id, model_name, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/models/{model_name}/train")
async def train_ml_model(
    model_name: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        require_supported_manual_training(model_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if (os.environ.get("TEMPORAL_HOST") or "").strip():
        try:
            started = await start_ml_model_training_workflow(org_id, model_name)
            if started.get("temporal"):
                return started
        except Exception:  # noqa: BLE001
            pass
    try:
        return await train_ml_model_for_org(org_id, model_name, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


class TrainingPermissionUpdate(BaseModel):
    state: str = Field(pattern="^(approved|paused|revoked|deferred)$")
    scope_digest: str = Field(min_length=64, max_length=64)


@router.get("/training-permissions")
async def list_training_permissions(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    from app.ml.training_consent import training_permission_inventory
    try:
        return await training_permission_inventory(org_id, settings)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Training permissions could not be verified") from exc


@router.post("/training-permissions/{model_name}")
async def update_training_permission(
    model_name: str,
    payload: TrainingPermissionUpdate,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    from app.ml.automatic_training import CONSENT_MANAGED_MODELS
    from app.ml.training_consent import save_training_consent
    if model_name not in CONSENT_MANAGED_MODELS:
        raise HTTPException(status_code=400, detail="Automatic training is not available for this model")
    try:
        return await asyncio.to_thread(save_training_consent, org_id, model_name, admin[0]["user_id"],
                                       payload.state, payload.scope_digest, settings)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
