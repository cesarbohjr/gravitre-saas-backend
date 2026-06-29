"""Multi-agent swarm coordinator API (STA-119)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.config import Settings, get_settings
from app.core.errors import error_detail
from app.middleware.entitlements import require_tier
from app.services.council_service import DecisionMethod
from app.services.swarm_coordinator_service import (
    SwarmCoordinatorError,
    SwarmSubtaskSpec,
    aggregate_swarm_run,
    cancel_swarm_run,
    get_swarm_run,
    list_swarm_runs,
    start_swarm,
)

router = APIRouter(
    prefix="/api/agent-swarm",
    tags=["agent-swarm"],
    dependencies=[Depends(require_tier("command"))],
)


class SwarmStartRequest(BaseModel):
    parent_agent_id: str = Field(..., alias="parentAgentId")
    objective: str = Field(..., min_length=1)
    subtasks: list[SwarmSubtaskSpec] = Field(..., min_length=1)
    decision_method: DecisionMethod = Field(default=DecisionMethod.MAJORITY_VOTE, alias="decisionMethod")

    model_config = {"populate_by_name": True}


def _client(settings: Settings):
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _raise_swarm(exc: SwarmCoordinatorError) -> None:
    code_map = {
        "NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "FORBIDDEN": status.HTTP_403_FORBIDDEN,
        "CONFLICT": status.HTTP_409_CONFLICT,
        "VALIDATION_ERROR": status.HTTP_400_BAD_REQUEST,
    }
    raise HTTPException(
        status_code=code_map.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=error_detail(str(exc), exc.code),
    ) from exc


@router.get("")
async def get_swarm_runs(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    return {"runs": list_swarm_runs(_client(settings), org_id, limit=limit)}


@router.get("/{swarm_run_id}")
async def get_swarm_run_route(
    swarm_run_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    try:
        return get_swarm_run(_client(settings), org_id, swarm_run_id)
    except SwarmCoordinatorError as exc:
        _raise_swarm(exc)


@router.post("/start")
async def post_swarm_start(
    body: SwarmStartRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = _client(settings)
    try:
        return await start_swarm(
            client,
            org_id=org_id,
            parent_agent_id=body.parent_agent_id,
            objective=body.objective,
            subtasks=body.subtasks,
            actor_id=user["user_id"],
            decision_method=body.decision_method.value,
            environment=environment,
            settings=settings,
        )
    except SwarmCoordinatorError as exc:
        _raise_swarm(exc)


@router.post("/{swarm_run_id}/aggregate")
async def post_swarm_aggregate(
    swarm_run_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    try:
        return await aggregate_swarm_run(_client(settings), org_id, swarm_run_id)
    except SwarmCoordinatorError as exc:
        _raise_swarm(exc)


@router.post("/{swarm_run_id}/cancel")
async def post_swarm_cancel(
    swarm_run_id: str,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    try:
        return cancel_swarm_run(_client(settings), org_id, swarm_run_id, user["user_id"])
    except SwarmCoordinatorError as exc:
        _raise_swarm(exc)
