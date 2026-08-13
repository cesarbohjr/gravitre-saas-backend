"""Admin API for honest business what-if simulation (CognitiveTurnKernel Phase 6)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_org_context, require_admin
from app.core.logging import get_logger
from app.services.cognitive_simulation_service import simulate_business_scenario

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin/cognitive-simulation", tags=["cognitive-simulation-admin"])


class WhatIfBody(BaseModel):
    scenario: str = Field(..., min_length=1)
    assumptions: list[str] | dict[str, Any] | None = None


@router.post("/what-if")
async def cognitive_simulation_what_if(
    body: WhatIfBody,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
) -> dict[str, Any]:
    """Run an honest qualitative what-if projection (Module C honesty fields always present)."""
    scenario = (body.scenario or "").strip()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scenario required")
    try:
        result = await simulate_business_scenario(
            org_id=org_id,
            scenario=scenario,
            assumptions=body.assumptions,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_simulation_failed error=%s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="cognitive simulation unavailable",
        ) from exc
    return result
