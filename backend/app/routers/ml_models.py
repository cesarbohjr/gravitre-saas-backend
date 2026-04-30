"""ML Models API: model registry, training, and inference."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_org_context
from app.ml.base import ModelStatus, ModelType
from app.ml.inference import get_inference_service
from app.ml.registry import get_model_registry
from app.workers.training_worker import create_training_worker

router = APIRouter(prefix="/api/ml", tags=["ml-models"])


class ModelCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    model_type: str = Field(..., pattern="^(classifier|fine_tuned_llm|anomaly_detector|forecaster)$")
    description: str | None = None
    dataset_id: str | None = None
    base_model: str | None = None
    task_type: str | None = None


class PredictRequest(BaseModel):
    inputs: list[dict[str, Any]]
    version: int | None = None
    return_probabilities: bool = False


class DeployRequest(BaseModel):
    version: int | None = None


@router.get("/models")
async def list_models(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    model_type: str | None = None,
    status: str | None = None,
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    registry = get_model_registry()
    mt = ModelType(model_type) if model_type else None
    ms = ModelStatus(status) if status else None
    models = await registry.list_models(org_id, model_type=mt, status=ms)
    return {
        "models": [
            {
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "model_type": m.model_type.value,
                "status": m.status.value,
                "current_version": m.current_version,
                "deployed_version": m.deployed_version,
                "dataset_id": m.dataset_id,
                "base_model": m.base_model,
                "created_at": m.created_at.isoformat(),
                "updated_at": m.updated_at.isoformat(),
            }
            for m in models
        ]
    }


@router.get("/models/{model_id}")
async def get_model(
    model_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    registry = get_model_registry()
    model = await registry.get_model(model_id)
    if not model or model.org_id != org_id:
        raise HTTPException(status_code=404, detail="Model not found")
    return {
        "id": model.id,
        "name": model.name,
        "description": model.description,
        "model_type": model.model_type.value,
        "status": model.status.value,
        "current_version": model.current_version,
        "deployed_version": model.deployed_version,
        "dataset_id": model.dataset_id,
        "base_model": model.base_model,
        "task_type": model.task_type,
        "created_at": model.created_at.isoformat(),
        "updated_at": model.updated_at.isoformat(),
        "versions": [
            {
                "version": v.version,
                "metrics": v.metrics.model_dump(),
                "artifact_size_bytes": v.artifact_size_bytes,
                "created_at": v.created_at.isoformat(),
            }
            for v in model.versions
        ],
    }


@router.post("/models", status_code=status.HTTP_201_CREATED)
async def create_model(
    body: ModelCreateRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    registry = get_model_registry()
    model = await registry.create_model(
        org_id=org_id,
        name=body.name,
        model_type=ModelType(body.model_type),
        description=body.description,
        dataset_id=body.dataset_id,
        base_model=body.base_model,
        task_type=body.task_type,
        created_by=user["user_id"],
    )
    return {"id": model.id, "name": model.name, "model_type": model.model_type.value, "status": model.status.value}


@router.post("/models/{model_id}/deploy")
async def deploy_model(
    model_id: str,
    body: DeployRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    registry = get_model_registry()
    model = await registry.get_model(model_id)
    if not model or model.org_id != org_id:
        raise HTTPException(status_code=404, detail="Model not found")
    await registry.deploy_version(model_id, body.version)
    return {"ok": True, "deployed_version": body.version or model.current_version}


@router.post("/models/{model_id}/predict")
async def predict(
    model_id: str,
    body: PredictRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    inference = get_inference_service()
    result = await inference.predict(
        org_id=org_id,
        model_id=model_id,
        inputs=body.inputs,
        version=body.version,
        return_probabilities=body.return_probabilities,
    )
    return {
        "model_id": result.model_id,
        "version": result.version,
        "predictions": result.predictions,
        "probabilities": result.probabilities,
        "latency_ms": result.latency_ms,
    }


@router.post("/train/start")
async def start_training(
    job_id: str,
    background_tasks: BackgroundTasks,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    worker = create_training_worker()
    background_tasks.add_task(worker.process_job, job_id)
    return {"ok": True, "message": "Training started"}
