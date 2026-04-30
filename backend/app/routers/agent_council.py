from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_org_context
from app.services.council_service import (
    AgentCouncilService,
    CouncilSession,
    DecisionMethod,
    get_council_service,
)

router = APIRouter(prefix="/api/agent-council", tags=["agent-council"])


class CouncilStartRequest(BaseModel):
    workflow_id: str | None = None
    run_id: str | None = None
    objective: str
    options: list[str]
    agents: list[dict] = Field(default_factory=list)
    evidence: dict | None = None
    decision_method: DecisionMethod = DecisionMethod.MAJORITY_VOTE
    max_rounds: int = 3


@router.post("/start", response_model=CouncilSession)
async def start_council(
    request: CouncilStartRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    council_service: AgentCouncilService = Depends(get_council_service),
) -> CouncilSession:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    return await council_service.start_council(
        org_id=org_id,
        workflow_id=request.workflow_id or str(uuid.uuid4()),
        run_id=request.run_id or str(uuid.uuid4()),
        objective=request.objective,
        options=request.options,
        agents=request.agents,
        evidence=request.evidence,
        decision_method=request.decision_method,
        max_rounds=request.max_rounds,
    )
