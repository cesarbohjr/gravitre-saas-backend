"""Admin intelligence dashboard API (v2 observability + v3 knowledge intelligence)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

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
