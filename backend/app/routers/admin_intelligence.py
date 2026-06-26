"""Admin intelligence dashboard API (v2 observability + v3 knowledge intelligence)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.knowledge_intelligence_service import load_admin_intelligence_snapshot
from app.services.entity_relationship_service import (
    list_relationships_for_entity,
    load_entity_relationships_snapshot,
)

router = APIRouter(prefix="/api/admin/intelligence", tags=["intelligence-admin"])


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
