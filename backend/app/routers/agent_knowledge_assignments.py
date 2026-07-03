"""Agent knowledge assignment CRUD API."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.services.agent_knowledge_assignment_service import get_agent_knowledge_assignment_service

router = APIRouter(prefix="/api/agents", tags=["agent-knowledge-assignments"])


class KnowledgeAssignmentResponse(BaseModel):
    id: str | None = None
    agent_id: str = Field(alias="agentId")
    source_type: str = Field(alias="sourceType")
    source_id: str = Field(alias="sourceId")
    label: str
    include_rules: list[Any] = Field(default_factory=list, alias="includeRules")
    exclude_rules: list[Any] = Field(default_factory=list, alias="excludeRules")
    sync_schedule: str | None = Field(default=None, alias="syncSchedule")
    owner_user_id: str | None = Field(default=None, alias="ownerUserId")
    confidence_score: float = Field(default=0.75, alias="confidenceScore")
    last_synced_at: str | None = Field(default=None, alias="lastSyncedAt")
    freshness_status: str = Field(default="unknown", alias="freshnessStatus")
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    from_config: bool = Field(default=False, alias="fromConfig")

    model_config = {"populate_by_name": True}


class KnowledgeAssignmentCreateRequest(BaseModel):
    source_type: str = Field(alias="sourceType")
    source_id: str = Field(alias="sourceId")
    label: str
    include_rules: list[Any] = Field(default_factory=list, alias="includeRules")
    exclude_rules: list[Any] = Field(default_factory=list, alias="excludeRules")
    sync_schedule: str | None = Field(default=None, alias="syncSchedule")
    owner_user_id: str | None = Field(default=None, alias="ownerUserId")
    confidence_score: float = Field(default=0.75, alias="confidenceScore")
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class KnowledgeAssignmentUpdateRequest(BaseModel):
    label: str | None = None
    include_rules: list[Any] | None = Field(default=None, alias="includeRules")
    exclude_rules: list[Any] | None = Field(default=None, alias="excludeRules")
    sync_schedule: str | None = Field(default=None, alias="syncSchedule")
    owner_user_id: str | None = Field(default=None, alias="ownerUserId")
    confidence_score: float | None = Field(default=None, alias="confidenceScore")
    freshness_status: str | None = Field(default=None, alias="freshnessStatus")
    enabled: bool | None = None
    metadata: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


def _to_response(row: dict[str, Any]) -> KnowledgeAssignmentResponse:
    return KnowledgeAssignmentResponse(
        id=row.get("id"),
        agent_id=row.get("agentId") or "",
        source_type=row.get("sourceType") or "",
        source_id=row.get("sourceId") or "",
        label=row.get("label") or "",
        include_rules=row.get("includeRules") or [],
        exclude_rules=row.get("excludeRules") or [],
        sync_schedule=row.get("syncSchedule"),
        owner_user_id=row.get("ownerUserId"),
        confidence_score=float(row.get("confidenceScore") or 0.75),
        last_synced_at=row.get("lastSyncedAt"),
        freshness_status=row.get("freshnessStatus") or "unknown",
        enabled=bool(row.get("enabled", True)),
        metadata=row.get("metadata") or {},
        from_config=bool(row.get("fromConfig")),
    )


@router.get("/{agent_id}/knowledge-assignments", response_model=list[KnowledgeAssignmentResponse])
async def list_knowledge_assignments(
    agent_id: UUID,
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    rows = get_agent_knowledge_assignment_service(settings).list_assignments(client, org_id, str(agent_id))
    return [_to_response(row) for row in rows]


@router.post(
    "/{agent_id}/knowledge-assignments",
    response_model=KnowledgeAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_assignment(
    agent_id: UUID,
    body: KnowledgeAssignmentCreateRequest,
    org_id: Annotated[str | None, Depends(get_org_context)],
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    _ = current_user
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = get_agent_knowledge_assignment_service(settings).create_assignment(
        client,
        org_id,
        str(agent_id),
        body.model_dump(by_alias=False),
    )
    return _to_response(row)


@router.patch("/{agent_id}/knowledge-assignments/{assignment_id}", response_model=KnowledgeAssignmentResponse)
async def update_knowledge_assignment(
    agent_id: UUID,
    assignment_id: UUID,
    body: KnowledgeAssignmentUpdateRequest,
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = get_agent_knowledge_assignment_service(settings).update_assignment(
        client,
        org_id,
        str(agent_id),
        str(assignment_id),
        body.model_dump(exclude_unset=True, by_alias=False),
    )
    return _to_response(row)


@router.delete("/{agent_id}/knowledge-assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_assignment(
    agent_id: UUID,
    assignment_id: UUID,
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    get_agent_knowledge_assignment_service(settings).delete_assignment(
        client,
        org_id,
        str(agent_id),
        str(assignment_id),
    )


@router.post("/{agent_id}/knowledge-assignments/sync-freshness", response_model=list[KnowledgeAssignmentResponse])
async def sync_knowledge_freshness(
    agent_id: UUID,
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    rows = get_agent_knowledge_assignment_service(settings).sync_freshness(client, org_id, str(agent_id))
    return [_to_response(row) for row in rows]
