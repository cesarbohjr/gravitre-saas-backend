"""Admin ML catalog API."""
from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
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
    from app.ml.training_consent import training_is_approved
    if not await training_is_approved(org_id, model_name, settings):
        raise HTTPException(status_code=409, detail="Approve the current training disclosure before requesting training")
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


class InferenceVerificationRequest(BaseModel):
    inputs: dict[str, Any]


@router.post("/models/{model_name}/verify-inference")
async def verify_ml_inference(
    model_name: str,
    payload: InferenceVerificationRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Run supplied real features through the same boundary as intelligence.

    Does not train, promote, change consent, or call generative providers. Input
    and output content are deliberately not persisted by this diagnostic.
    """
    import json
    from datetime import datetime, timezone
    from app.ml.model_catalog import (
        GRAVITRE_ML_CATALOG, IMPLEMENTED_ADVANCED_MODELS, infer_catalog_capability,
    )

    if model_name not in GRAVITRE_ML_CATALOG:
        raise HTTPException(status_code=404, detail="Unknown catalog model")
    if len(json.dumps(payload.inputs, default=str)) > 65536:
        raise HTTPException(status_code=413, detail="Inference inputs exceed 64 KiB")
    if (GRAVITRE_ML_CATALOG[model_name]["status"].value != "trained"
            and model_name not in IMPLEMENTED_ADVANCED_MODELS):
        raise HTTPException(status_code=400, detail="Model inference is not implemented")
    result = await infer_catalog_capability(org_id, model_name, payload.inputs, settings=settings, source="diagnostic")
    return {
        "org_id": org_id, "checked_at": datetime.now(timezone.utc).isoformat(),
        "inference_health": "verified" if result.get("status") == "ok" and not result.get("used_fallback") else "not_verified",
        "evidence_scope": "This request only; does not establish model accuracy, outcomes, or other surfaces.",
        "result": result,
    }


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
    background_tasks: BackgroundTasks,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    from app.ml.automatic_training import CONSENT_MANAGED_MODELS
    from app.ml.training_consent import save_training_consent
    if model_name not in {*CONSENT_MANAGED_MODELS, "multimodal_router", "diffusion_model", "federated_learning"}:
        raise HTTPException(status_code=400, detail="No implemented processing permission for this model")
    try:
        result = await asyncio.to_thread(save_training_consent, org_id, model_name, admin[0]["user_id"],
                                        payload.state, payload.scope_digest, settings)
        if payload.state == "approved" and model_name in {*CONSENT_MANAGED_MODELS, "federated_learning"}:
            from app.services.company_intelligence_orchestrator import run_company_intelligence_for_org_sync
            # Reuse the existing guarded job immediately after approval. Paid
            # generation/media execution is never started by this callback.
            background_tasks.add_task(run_company_intelligence_for_org_sync, org_id, settings)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/lifecycle")
async def list_model_lifecycle(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """All 26 entries remain accounted for, including dormant/blocked models."""
    from app.ml.lifecycle import resolve_lifecycle
    from app.ml.training_consent import training_permission_inventory

    dashboard = await build_ml_catalog_dashboard(org_id, settings=settings, include_advanced=True)
    try:
        permissions = await training_permission_inventory(org_id, settings)
        by_model = {row["model_name"]: row for row in permissions["models"]}
    except Exception:
        by_model = {}
    models = {}
    for name, inventory in dashboard["inventory"].items():
        models[name] = resolve_lifecycle(name, dashboard["orgTrainingStatus"].get(name) or {},
                                        by_model.get(name), inventory.get("recent_execution_evidence"))
    return {"models": models, "scope": "backend_model_lifecycle_only",
            "phase1_acceptance": "not_complete", "phase2_acceptance": "not_complete",
            "note": "Execution evidence does not prove accuracy, downstream consumption, or business outcomes."}


@router.get("/federation/consent/{tenant_id}", include_in_schema=False)
def federation_consent_readback(
    tenant_id: str,
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Consent-only service credential; cannot read model weights or records."""
    import hmac
    from uuid import UUID
    from app.ml.federated_learning import verified_privacy_profile
    from app.ml.training_consent import consent_is_approved, load_training_consents
    from app.core.safe_dict import safe_normalize_stored_dict
    secret = settings.federated_consent_service_secret
    if not isinstance(secret,str) or len(secret) < 32 or not hmac.compare_digest(authorization or '', 'Bearer '+secret):
        raise HTTPException(status_code=403,detail="Consent service credential required")
    try:
        tenant_id = str(UUID(tenant_id))
        _, digest = verified_privacy_profile(settings)
        consents = load_training_consents(tenant_id,settings)
        approval = safe_normalize_stored_dict(consents.get('federated_learning'))
        return {'org_id':tenant_id, 'audit_digest':digest,
                'approved':consent_is_approved(consents,'federated_learning') and approval.get('audit_digest') == digest,
                'ranker_approved':consent_is_approved(consents,'retrieval_ranker')}
    except Exception:
        return {'org_id':tenant_id,'approved':False,'ranker_approved':False,'audit_digest':None}
