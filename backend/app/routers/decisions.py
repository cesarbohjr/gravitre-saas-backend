from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_org_context
from app.services.decision_service import (
    DecisionPath,
    DecisionResult,
    DecisionService,
    DecisionType,
    get_decision_service,
)

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


class DecisionContext(BaseModel):
    workflow_id: str | None = None
    run_id: str | None = None
    node_id: str | None = None
    objective: str
    input_data: dict = Field(default_factory=dict)
    paths: list[DecisionPath] = Field(default_factory=list)
    decision_type: DecisionType = DecisionType.HYBRID
    rules: list[dict] | None = None
    rag_context: str | None = None


@router.post("/evaluate", response_model=DecisionResult)
async def evaluate_decision(
    context: DecisionContext,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    decision_service: DecisionService = Depends(get_decision_service),
) -> DecisionResult:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    return await decision_service.evaluate(
        org_id=org_id,
        workflow_id=context.workflow_id or str(uuid.uuid4()),
        run_id=context.run_id or str(uuid.uuid4()),
        node_id=context.node_id or "decision-node",
        objective=context.objective,
        input_data=context.input_data,
        available_paths=context.paths,
        decision_type=context.decision_type,
        rules=context.rules,
        rag_context=context.rag_context,
    )
