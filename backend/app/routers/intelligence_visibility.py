"""Wave E visibility APIs — /api/intelligence/visibility/*"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_org_context, require_admin, require_org_member
from app.config import Settings, get_settings
from app.services.intelligence_visibility_service import get_intelligence_visibility_service

router = APIRouter(prefix="/api/intelligence/visibility", tags=["intelligence-visibility"])


def _require_visibility_enabled(settings: Settings) -> None:
    if not getattr(settings, "intelligence_visibility_enabled", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intelligence visibility is disabled for this environment.",
        )


@router.get("/explainability")
async def get_visibility_explainability(
    org_id: Annotated[str, Depends(get_org_context)],
    _member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _require_visibility_enabled(settings)
    service = get_intelligence_visibility_service(settings)
    maturity = await service.get_executive_summary(org_id)
    return {
        "status": "ok",
        "org_id": org_id,
        "schema": "decision_transparency_envelope_v1",
        "advisory_only": True,
        "maturity": maturity.get("maturity"),
        "domain_health": maturity.get("domain_health"),
        "trust_health": await service.get_trust_health(org_id),
    }


@router.get("/trust-health")
async def get_visibility_trust_health(
    org_id: Annotated[str, Depends(get_org_context)],
    _member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _require_visibility_enabled(settings)
    return await get_intelligence_visibility_service(settings).get_trust_health(org_id)


@router.get("/learning-health")
async def get_visibility_learning_health(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _require_visibility_enabled(settings)
    return await get_intelligence_visibility_service(settings).get_learning_health(org_id)


@router.get("/domain-health")
async def get_visibility_domain_health(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _require_visibility_enabled(settings)
    return await get_intelligence_visibility_service(settings).get_domain_health(org_id)


@router.get("/knowledge-health")
async def get_visibility_knowledge_health(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _require_visibility_enabled(settings)
    return await get_intelligence_visibility_service(settings).get_knowledge_health(org_id)


@router.get("/executive")
async def get_visibility_executive_summary(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _require_visibility_enabled(settings)
    return await get_intelligence_visibility_service(settings).get_executive_summary(org_id)


@router.get("/maturity")
async def get_visibility_maturity(
    org_id: Annotated[str, Depends(get_org_context)],
    _member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _require_visibility_enabled(settings)
    from app.services.intelligence_maturity_service import get_intelligence_maturity_service

    maturity = await get_intelligence_maturity_service().compute_maturity(org_id, settings=settings)
    return {"status": "ok", "org_id": org_id, "maturity": maturity}


@router.get("/agents/{agent_id}")
async def get_visibility_agent_profile(
    agent_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _require_visibility_enabled(settings)
    return await get_intelligence_visibility_service(settings).get_agent_visibility(org_id, agent_id)
