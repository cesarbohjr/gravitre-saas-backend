from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_org_context
from app.services.optimization_service import Recommendation, OptimizationService, get_optimization_service

router = APIRouter(prefix="/api/optimization", tags=["optimization"])


class AnalyzeWorkflowRequest(BaseModel):
    workflow_id: str
    days: int = Field(default=30, ge=1, le=365)


@router.post("/analyze", response_model=list[Recommendation])
async def analyze_workflow(
    body: AnalyzeWorkflowRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    optimization_service: OptimizationService = Depends(get_optimization_service),
) -> list[Recommendation]:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    return await optimization_service.analyze_workflow(
        org_id=org_id,
        workflow_id=body.workflow_id,
        days=body.days,
    )
