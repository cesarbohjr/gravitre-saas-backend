"""Model Studio "Improve agent": apply selected improvements to one agent."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.db import get_supabase
from app.services.agent_improvement_service import (
    MAX_INSTRUCTION_CHARS,
    MAX_INSTRUCTION_NAME_CHARS,
    MAX_KNOWLEDGE_SOURCES,
    ImprovementRequest,
    apply_agent_improvements,
    read_agent_improvement_state,
)

router = APIRouter(prefix="/api/agents", tags=["agent-improvements"])


class InstructionImprovement(BaseModel):
    name: str | None = Field(default=None, max_length=MAX_INSTRUCTION_NAME_CHARS)
    content: str = Field(..., min_length=1, max_length=MAX_INSTRUCTION_CHARS)


class AgentImprovementsBody(BaseModel):
    instruction: InstructionImprovement | None = None
    model: str | None = Field(default=None, max_length=100)
    trained_model_id: str | None = Field(default=None, alias="trainedModelId", max_length=64)
    knowledge_source_ids: list[str] = Field(
        default_factory=list, alias="knowledgeSourceIds", max_length=MAX_KNOWLEDGE_SOURCES
    )

    model_config = {"populate_by_name": True, "protected_namespaces": ()}


@router.get("/{agent_id}/improvements")
def get_agent_improvement_state(
    agent_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    client: Annotated[Any, Depends(get_supabase)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    return read_agent_improvement_state(client, org_id, agent_id)


@router.post("/{agent_id}/improvements")
def post_agent_improvements(
    agent_id: str,
    body: AgentImprovementsBody,
    admin: Annotated[tuple, Depends(require_admin)],
    client: Annotated[Any, Depends(get_supabase)],
) -> dict:
    user, org_id = admin
    request = ImprovementRequest(
        instruction_content=body.instruction.content if body.instruction else None,
        instruction_name=body.instruction.name if body.instruction else None,
        model=body.model,
        trained_model_id=body.trained_model_id,
        knowledge_source_ids=list(body.knowledge_source_ids),
    )
    return apply_agent_improvements(
        client,
        org_id=org_id,
        agent_id=agent_id,
        actor_id=str(user.get("user_id") or user.get("sub") or ""),
        request=request,
    )
