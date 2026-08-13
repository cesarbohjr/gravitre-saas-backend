"""Department umbrella → recursive sub-agents API."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.department_subagent_service import (
    DepartmentSubagentError,
    get_department_subagent_service,
)

router = APIRouter(prefix="/api/department-subagents", tags=["department-subagents"])


class SpawnSubagentRequest(BaseModel):
    umbrella_agent_id: str = Field(..., alias="umbrellaAgentId", min_length=1)
    name: str = Field(..., min_length=1)
    role: str | None = None
    purpose: str | None = None

    model_config = {"populate_by_name": True}


def _raise(exc: DepartmentSubagentError) -> None:
    code_map = {
        "NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "VALIDATION_ERROR": status.HTTP_400_BAD_REQUEST,
        "INTERNAL": status.HTTP_500_INTERNAL_SERVER_ERROR,
    }
    raise HTTPException(status_code=code_map.get(exc.code, status.HTTP_400_BAD_REQUEST), detail=str(exc)) from exc


@router.get("/{umbrella_agent_id}")
async def list_department_subagents(
    umbrella_agent_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    recursive: Annotated[bool, Query()] = True,
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    try:
        return get_department_subagent_service(settings).list_department_subagents(
            org_id,
            umbrella_agent_id,
            recursive=recursive,
        )
    except DepartmentSubagentError as exc:
        _raise(exc)


@router.post("")
async def spawn_department_subagent(
    body: SpawnSubagentRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    actor_id = str(user.get("user_id") or user.get("id") or "") or None
    try:
        return get_department_subagent_service(settings).spawn_department_subagent(
            org_id,
            body.umbrella_agent_id,
            name=body.name,
            role=body.role,
            purpose=body.purpose,
            actor_id=actor_id,
        )
    except DepartmentSubagentError as exc:
        _raise(exc)
