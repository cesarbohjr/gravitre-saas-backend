"""Admin ML catalog API."""
from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.ml.model_catalog import (
    get_catalog,
    get_org_model_status,
    train_ml_model_for_org,
)
from app.services.strategy_performance_ledger import get_strategy_performance_ledger
from app.temporal.starters import start_ml_model_training_workflow

router = APIRouter(prefix="/api/admin/ml", tags=["ml-admin"])


@router.get("/models")
async def list_ml_catalog(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    catalog = get_catalog()
    org_status: dict[str, Any] = {}
    for name, meta in catalog.items():
        if meta.get("status") == "trained":
            try:
                org_status[name] = await get_org_model_status(org_id, name, settings=settings)
            except ValueError:
                continue
    outcome_scores = await get_strategy_performance_ledger(settings).load_model_outcome_scores(org_id)
    return {"catalog": catalog, "orgTrainingStatus": org_status, "outcomeScores": outcome_scores}


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
