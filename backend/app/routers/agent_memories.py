"""Agent memory CRUD API (STA-49)."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.services.agent_memory_service import (
    create_agent_memory,
    delete_agent_memory,
    get_agent_memory,
    list_agent_memories,
    search_agent_memories,
    update_agent_memory,
)
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/agents", tags=["agent-memories"])


class AgentMemoryResponse(BaseModel):
    id: str
    agent_id: str = Field(alias="agentId")
    content: str
    category: str
    provenance: str | None = None
    source: str | None = None
    confidence: float
    usage_count: int = Field(alias="usageCount")
    editable: bool
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    score: float | None = None

    model_config = {"populate_by_name": True}


class AgentMemoryCreateRequest(BaseModel):
    content: str
    category: str | None = "fact"
    provenance: str | None = None
    source: str | None = None
    confidence: float = 100
    editable: bool = True


class AgentMemoryUpdateRequest(BaseModel):
    content: str | None = None
    category: str | None = None
    provenance: str | None = None
    source: str | None = None
    confidence: float | None = None
    editable: bool | None = None


class AgentMemorySearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=10, alias="topK", ge=1, le=50)
    category: str | None = None


def _to_response(row: dict) -> AgentMemoryResponse:
    return AgentMemoryResponse(
        id=row["id"],
        agent_id=row["agentId"],
        content=row["content"],
        category=row["category"],
        provenance=row.get("provenance"),
        source=row.get("source") or row.get("provenance"),
        confidence=row["confidence"],
        usage_count=row["usageCount"],
        editable=row["editable"],
        created_at=row.get("createdAt"),
        updated_at=row.get("updatedAt"),
        score=row.get("score"),
    )


@router.get("/{agent_id}/memories", response_model=list[AgentMemoryResponse])
async def list_memories_route(
    agent_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> list[AgentMemoryResponse]:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    rows = list_agent_memories(client, org_id, str(agent_id), category=category, query=q)
    return [_to_response(row) for row in rows]


@router.get("/{agent_id}/memories/{memory_id}", response_model=AgentMemoryResponse)
async def get_memory_route(
    agent_id: UUID,
    memory_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AgentMemoryResponse:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _to_response(get_agent_memory(client, org_id, str(agent_id), str(memory_id)))


@router.post("/{agent_id}/memories", response_model=AgentMemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory_route(
    agent_id: UUID,
    body: AgentMemoryCreateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AgentMemoryResponse:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = create_agent_memory(
        settings,
        client,
        org_id,
        str(agent_id),
        user_id=current_user["user_id"],
        content=body.content,
        category=body.category,
        provenance=body.provenance or body.source,
        confidence=body.confidence,
        editable=body.editable,
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="agent_memory.create",
        resource_type="agent_memory",
        resource_id=row["id"],
        metadata={"agent_id": str(agent_id), "category": row["category"]},
    )
    return _to_response(row)


@router.patch("/{agent_id}/memories/{memory_id}", response_model=AgentMemoryResponse)
async def update_memory_route(
    agent_id: UUID,
    memory_id: UUID,
    body: AgentMemoryUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AgentMemoryResponse:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = update_agent_memory(
        settings,
        client,
        org_id,
        str(agent_id),
        str(memory_id),
        content=body.content,
        category=body.category,
        provenance=body.provenance if body.provenance is not None else body.source,
        confidence=body.confidence,
        editable=body.editable,
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="agent_memory.update",
        resource_type="agent_memory",
        resource_id=str(memory_id),
        metadata={"agent_id": str(agent_id)},
    )
    return _to_response(row)


@router.delete("/{agent_id}/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory_route(
    agent_id: UUID,
    memory_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    delete_agent_memory(client, org_id, str(agent_id), str(memory_id))
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="agent_memory.delete",
        resource_type="agent_memory",
        resource_id=str(memory_id),
        metadata={"agent_id": str(agent_id)},
    )


@router.post("/{agent_id}/memories/search", response_model=list[AgentMemoryResponse])
async def search_memories_route(
    agent_id: UUID,
    body: AgentMemorySearchRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[AgentMemoryResponse]:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    rows = search_agent_memories(
        settings,
        client,
        org_id,
        str(agent_id),
        query=body.query,
        top_k=body.top_k,
        category=body.category,
    )
    return [_to_response(row) for row in rows]
