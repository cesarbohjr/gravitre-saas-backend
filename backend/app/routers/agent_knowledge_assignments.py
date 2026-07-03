"""Agent knowledge source assignment API (admin-managed, assignment-scoped)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_org_context, require_admin
from app.db import get_supabase
from app.services.agent_capability_profile_service import get_agent_capability_profile_service
from app.services.agent_knowledge_assignment_service import get_agent_knowledge_assignment_service
from app.services.agent_knowledge_provenance_service import get_agent_knowledge_provenance_service
from app.services.agent_knowledge_sync_service import get_agent_knowledge_sync_service
from app.services.knowledge_source_types import validate_source_type

router = APIRouter(prefix="/api/agents", tags=["agent-knowledge-assignments"])


@router.get("/demo-knowledge-workflows")
async def list_demo_knowledge_workflows():
    from app.marketplace.demo_workflow_templates import list_agent_knowledge_demo_workflows

    return {"workflows": list_agent_knowledge_demo_workflows()}


class KnowledgeAssignmentCreate(BaseModel):
    source_type: str = Field(..., alias="sourceType")
    source_id: str = Field(..., alias="sourceId")
    label: str
    include_rules: list[str] = Field(default_factory=list, alias="includeRules")
    exclude_rules: list[str] = Field(default_factory=list, alias="excludeRules")
    sync_schedule: str | None = Field(default=None, alias="syncSchedule")
    sync_frequency: str | None = Field(default="daily", alias="syncFrequency")
    sync_enabled: bool = Field(default=True, alias="syncEnabled")
    connector_id: str | None = Field(default=None, alias="connectorId")
    external_source_url: str | None = Field(default=None, alias="externalSourceUrl")
    owning_department: str | None = Field(default=None, alias="owningDepartment")
    read_scope: list[str] = Field(default_factory=lambda: ["read"], alias="readScope")
    write_scope: list[str] = Field(default_factory=list, alias="writeScope")
    learn_scope: list[str] = Field(default_factory=lambda: ["read", "summarize"], alias="learnScope")
    tags_required: list[str] = Field(default_factory=list, alias="tagsRequired")
    tags_excluded: list[str] = Field(default_factory=list, alias="tagsExcluded")
    freshness_policy: dict[str, Any] = Field(default_factory=dict, alias="freshnessPolicy")
    permission_policy: dict[str, Any] = Field(default_factory=dict, alias="permissionPolicy")
    provenance_required: bool = Field(default=True, alias="provenanceRequired")
    owner_user_id: str | None = Field(default=None, alias="ownerUserId")
    confidence_score: float = Field(default=0.75, alias="confidenceScore")
    freshness_status: str = Field(default="unknown", alias="freshnessStatus")
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class KnowledgeAssignmentUpdate(BaseModel):
    label: str | None = None
    include_rules: list[str] | None = Field(default=None, alias="includeRules")
    exclude_rules: list[str] | None = Field(default=None, alias="excludeRules")
    sync_schedule: str | None = Field(default=None, alias="syncSchedule")
    sync_frequency: str | None = Field(default=None, alias="syncFrequency")
    sync_enabled: bool | None = Field(default=None, alias="syncEnabled")
    connector_id: str | None = Field(default=None, alias="connectorId")
    external_source_url: str | None = Field(default=None, alias="externalSourceUrl")
    owning_department: str | None = Field(default=None, alias="owningDepartment")
    read_scope: list[str] | None = Field(default=None, alias="readScope")
    write_scope: list[str] | None = Field(default=None, alias="writeScope")
    learn_scope: list[str] | None = Field(default=None, alias="learnScope")
    tags_required: list[str] | None = Field(default=None, alias="tagsRequired")
    tags_excluded: list[str] | None = Field(default=None, alias="tagsExcluded")
    freshness_policy: dict[str, Any] | None = Field(default=None, alias="freshnessPolicy")
    permission_policy: dict[str, Any] | None = Field(default=None, alias="permissionPolicy")
    provenance_required: bool | None = Field(default=None, alias="provenanceRequired")
    owner_user_id: str | None = Field(default=None, alias="ownerUserId")
    confidence_score: float | None = Field(default=None, alias="confidenceScore")
    freshness_status: str | None = Field(default=None, alias="freshnessStatus")
    enabled: bool | None = None
    metadata: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


class TestRetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1)


def _assignment_service():
    return get_agent_knowledge_assignment_service()


@router.get("/{agent_id}/knowledge-assignments")
async def list_knowledge_assignments(
    agent_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    client=Depends(get_supabase),
):
    return {"assignments": _assignment_service().list_assignments(client, org_id, agent_id)}


@router.get("/{agent_id}/knowledge-sources")
async def list_knowledge_sources_alias(
    agent_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    client=Depends(get_supabase),
):
    return {"assignments": _assignment_service().list_assignments(client, org_id, agent_id)}


@router.post("/{agent_id}/knowledge-assignments", status_code=status.HTTP_201_CREATED)
async def create_knowledge_assignment(
    agent_id: str,
    body: KnowledgeAssignmentCreate,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    client=Depends(get_supabase),
):
    validate_source_type(body.source_type)
    user, _org = admin
    payload = body.model_dump(by_alias=False)
    payload["created_by"] = user.get("user_id") or user.get("sub")
    return _assignment_service().create_assignment(client, org_id, agent_id, payload)


@router.post("/{agent_id}/knowledge-sources", status_code=status.HTTP_201_CREATED)
async def create_knowledge_source_alias(
    agent_id: str,
    body: KnowledgeAssignmentCreate,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    client=Depends(get_supabase),
):
    return await create_knowledge_assignment(agent_id, body, org_id, admin, client)


@router.patch("/{agent_id}/knowledge-assignments/{assignment_id}")
async def update_knowledge_assignment(
    agent_id: str,
    assignment_id: str,
    body: KnowledgeAssignmentUpdate,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    client=Depends(get_supabase),
):
    payload = {k: v for k, v in body.model_dump(by_alias=False).items() if v is not None}
    return _assignment_service().update_assignment(client, org_id, agent_id, assignment_id, payload)


@router.delete("/{agent_id}/knowledge-assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_assignment(
    agent_id: str,
    assignment_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    client=Depends(get_supabase),
):
    _assignment_service().delete_assignment(client, org_id, agent_id, assignment_id)


@router.post("/{agent_id}/knowledge-assignments/{assignment_id}/sync")
async def sync_knowledge_assignment(
    agent_id: str,
    assignment_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    client=Depends(get_supabase),
):
    user, _org = admin
    return await get_agent_knowledge_sync_service().sync_assignment(
        client,
        org_id,
        agent_id,
        assignment_id,
        actor_id=str(user.get("user_id") or user.get("sub") or ""),
    )


@router.get("/{agent_id}/capabilities")
async def get_agent_capabilities(
    agent_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    client=Depends(get_supabase),
):
    return get_agent_capability_profile_service().build_profile(client, org_id, agent_id)


@router.get("/{agent_id}/knowledge-assignments/{assignment_id}/provenance")
async def get_assignment_provenance(
    agent_id: str,
    assignment_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    client=Depends(get_supabase),
):
    return get_agent_knowledge_provenance_service().explain_provenance(
        client, org_id, agent_id, assignment_id
    )


@router.get("/{agent_id}/memory-lineage")
async def get_memory_lineage(
    agent_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    client=Depends(get_supabase),
):
    return {"lineage": get_agent_knowledge_provenance_service().list_lineage(client, org_id, agent_id)}


@router.post("/{agent_id}/knowledge-assignments/test-retrieval")
async def test_knowledge_retrieval(
    agent_id: str,
    body: TestRetrievalRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    client=Depends(get_supabase),
):
    return await _assignment_service().test_retrieval(
        client, org_id, agent_id, body.query
    )
