"""Internal agent collaboration API (department → department handoffs).

EXTERNAL A2A is rejected at the schema boundary — Phase 4 gated.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.core.errors import error_detail
from app.middleware.entitlements import require_tier
from app.services.agent_collaboration_service import (
    CollaborationHandoffError,
    CollaborationResponseContract,
    CollaborationTaskHandoff,
    CollaborationTrail,
    RankedContextItem,
    execute_internal_collaboration_handoff,
)
from app.workflows.repository import get_supabase_client

router = APIRouter(
    prefix="/api/agent-collaboration",
    tags=["agent-collaboration"],
    dependencies=[Depends(require_tier("command"))],
)


class CollaborationHandoffRequest(BaseModel):
    originating_agent_id: str = Field(..., alias="originatingAgentId")
    receiving_agent_id: str = Field(..., alias="receivingAgentId")
    task: str = Field(..., min_length=1)
    originating_claim: dict[str, Any] = Field(default_factory=dict, alias="originatingClaim")
    ranked_context: list[RankedContextItem] | None = Field(default=None, alias="rankedContext")
    extra_context_sources: list[dict[str, Any]] | None = Field(
        default=None, alias="extraContextSources"
    )
    response_contract: CollaborationResponseContract | None = Field(
        default=None, alias="responseContract"
    )
    workflow_run_id: str | None = Field(default=None, alias="workflowRunId")
    connected_integrations: list[str] = Field(default_factory=list, alias="connectedIntegrations")
    run_reconciliation: bool = Field(default=True, alias="runReconciliation")
    # External A2A intentionally omitted — not accepted on this API.

    model_config = {"populate_by_name": True}


@router.post("/handoff", response_model=CollaborationTrail)
async def start_internal_collaboration_handoff(
    request: CollaborationHandoffRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CollaborationTrail:
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    actor_id = str(user.get("id") or user.get("sub") or "")
    if not actor_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated actor required",
        )

    from app.services.agent_collaboration_service import build_ranked_context_for_handoff

    ranked = request.ranked_context
    if not ranked:
        ranked = build_ranked_context_for_handoff(
            task=request.task,
            originating_claim=request.originating_claim,
            extra_sources=request.extra_context_sources,
        )

    try:
        handoff = CollaborationTaskHandoff(
            originating_agent_id=request.originating_agent_id,
            receiving_agent_id=request.receiving_agent_id,
            task=request.task,
            originating_claim=request.originating_claim,
            ranked_context=list(ranked),
            response_contract=request.response_contract or CollaborationResponseContract(),
            trust_boundary="internal",
            workflow_run_id=request.workflow_run_id,
            connected_integrations=request.connected_integrations,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail(str(exc), "EXTERNAL_A2A_GATED"),
        ) from exc

    client = get_supabase_client(settings)
    try:
        return await execute_internal_collaboration_handoff(
            settings,
            org_id=org_id,
            actor_id=actor_id,
            handoff=handoff,
            client=client,
            run_reconciliation=request.run_reconciliation,
        )
    except CollaborationHandoffError as exc:
        code_map = {
            "ORIGIN_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "RECEIVER_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "EXTERNAL_A2A_GATED": status.HTTP_403_FORBIDDEN,
            "ORIGIN_INACTIVE": status.HTTP_409_CONFLICT,
            "RECEIVER_INACTIVE": status.HTTP_409_CONFLICT,
        }
        raise HTTPException(
            status_code=code_map.get(exc.code, status.HTTP_400_BAD_REQUEST),
            detail=error_detail(str(exc), exc.code),
        ) from exc
