from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_org_context
from app.services.execution_service import ExecutionService, RunResult, get_execution_service

router = APIRouter(prefix="/api/execution", tags=["execution"])


class ExecuteWorkflowRequest(BaseModel):
    workflow_id: str
    run_id: str | None = None
    parameters: dict | None = Field(default_factory=dict)


@router.post("/workflows/execute", response_model=RunResult)
async def execute_workflow(
    body: ExecuteWorkflowRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    execution_service: ExecutionService = Depends(get_execution_service),
) -> RunResult:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    run_id = body.run_id or str(uuid.uuid4())
    return await execution_service.execute_workflow(
        org_id=org_id,
        workflow_id=body.workflow_id,
        run_id=run_id,
        parameters=body.parameters or {},
    )
