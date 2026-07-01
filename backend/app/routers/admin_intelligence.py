"""Admin intelligence dashboard API (v2 observability + v3 knowledge intelligence)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.knowledge_intelligence_service import load_admin_intelligence_snapshot
from app.services.response_evaluation_service import load_admin_response_evaluations
from app.services.entity_relationship_service import (
    list_relationships_for_entity,
    load_entity_relationships_snapshot,
)
from app.services.outcome_attribution_service import get_outcome_attribution_service
from app.services.company_intelligence_orchestrator import get_company_intelligence_orchestrator
from app.services.intelligence_engine_settings import (
    load_intelligence_engine_settings,
    save_intelligence_engine_settings,
    PERFORMANCE_MODES,
)
from app.services.performance_dashboard_service import load_performance_dashboard
from app.services.business_impact_service import load_business_impact_snapshot

router = APIRouter(prefix="/api/admin/intelligence", tags=["intelligence-admin"])


@router.get("/learning-progress")
async def get_learning_progress(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
) -> dict[str, Any]:
    """Usage counts vs company-intelligence thresholds (honest new-org progress)."""
    return await get_company_intelligence_orchestrator().get_learning_progress(org_id)


@router.get("/snapshot")
async def get_intelligence_snapshot(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Org-scoped intelligence snapshot for the admin dashboard."""
    return await load_admin_intelligence_snapshot(settings, org_id)


@router.get("/relationships")
async def get_entity_relationships(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    entity_type: str | None = Query(default=None, alias="entityType"),
    entity_id: str | None = Query(default=None, alias="entityId"),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    if entity_type and entity_id:
        return await list_relationships_for_entity(
            org_id, entity_type, entity_id, settings=settings
        )
    return await load_entity_relationships_snapshot(org_id, settings=settings, limit=limit)


@router.get("/evaluations")
async def get_response_evaluations(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    since_days: int | None = Query(default=None, ge=1, le=365, alias="sinceDays"),
) -> dict[str, Any]:
    """Org-scoped v7 response evaluations and retrieval ranker status."""
    return await load_admin_response_evaluations(
        settings,
        org_id,
        limit=limit,
        offset=offset,
        since_days=since_days,
    )


@router.get("/outcomes")
async def get_outcome_summaries(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """v8 org-scoped outcome-linked learning summaries (correlational, not RL)."""
    service = get_outcome_attribution_service(settings)
    return await service.load_admin_outcomes_snapshot(org_id, settings=settings)


class IntelligenceEngineSettingsUpdate(BaseModel):
    validation_enabled: bool | None = None
    reranking_enabled: bool | None = None
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    max_chunks: int | None = Field(default=None, ge=1, le=50)
    connector_timeout_seconds: int | None = Field(default=None, ge=5, le=300)
    performance_mode: str | None = None


class PerformanceModeUpdate(BaseModel):
    mode: str = Field(..., pattern="^(speed_priority|balanced|accuracy_priority)$")


@router.get("/engine-settings")
async def get_engine_settings(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    current = await load_intelligence_engine_settings(org_id, settings)
    return {
        "validationEnabled": current.validation_enabled,
        "rerankingEnabled": current.reranking_enabled,
        "confidenceThreshold": current.confidence_threshold,
        "maxChunks": current.max_chunks,
        "connectorTimeoutSeconds": current.connector_timeout_seconds,
        "performanceMode": current.performance_mode,
    }


@router.patch("/engine-settings")
async def update_engine_settings(
    body: IntelligenceEngineSettingsUpdate,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    payload = body.model_dump(exclude_none=True)
    saved = await save_intelligence_engine_settings(org_id, settings, payload)
    return {
        "validationEnabled": saved.validation_enabled,
        "rerankingEnabled": saved.reranking_enabled,
        "confidenceThreshold": saved.confidence_threshold,
        "maxChunks": saved.max_chunks,
        "connectorTimeoutSeconds": saved.connector_timeout_seconds,
        "performanceMode": saved.performance_mode,
    }


@router.get("/performance-mode")
async def get_performance_mode(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    current = await load_intelligence_engine_settings(org_id, settings)
    return {"mode": current.performance_mode}


@router.patch("/performance-mode")
async def update_performance_mode(
    body: PerformanceModeUpdate,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    if body.mode not in PERFORMANCE_MODES:
        return {"mode": "balanced"}
    saved = await save_intelligence_engine_settings(org_id, settings, {"performance_mode": body.mode})
    return {"mode": saved.performance_mode}


@router.get("/business-impact")
async def get_business_impact_snapshot(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Revenue Risk Radar + Business Impact Score over existing v8/v10 signals."""
    return await load_business_impact_snapshot(org_id, settings=settings)


@router.get("/performance")
async def get_performance_dashboard(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    period: str = Query(default="24h", pattern="^(1h|24h|7d)$"),
) -> dict[str, Any]:
    return await load_performance_dashboard(settings, org_id, period=period)
