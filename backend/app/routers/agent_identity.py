"""Admin API for Agent Identity IAM records and delegation grants."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin, require_org_member
from app.config import Settings, get_settings
from app.services.agent_identity_service import (
    build_identity_status,
    create_delegation_grant,
    get_agent_identity_record,
    list_delegation_grants,
    revoke_delegation_grant,
    serialize_identity_record,
    upsert_agent_identity_record,
)

router = APIRouter(prefix="/api/agents", tags=["agent-identity"])


class AgentIdentityUpsert(BaseModel):
    department_id: str | None = Field(default=None, alias="departmentId")
    agent_role: str | None = Field(default=None, alias="agentRole")
    trust_level: str | None = Field(default=None, alias="trustLevel")
    allowed_tool_patterns: list[str] = Field(default_factory=list, alias="allowedToolPatterns")
    allowed_action_kinds: list[str] = Field(default_factory=list, alias="allowedActionKinds")
    allowed_data_scopes: list[str] = Field(default_factory=list, alias="allowedDataScopes")
    max_actions_per_day: int | None = Field(default=None, alias="maxActionsPerDay")
    max_tokens_per_day: int | None = Field(default=None, alias="maxTokensPerDay")
    max_spend_usd_per_day: float | None = Field(default=None, alias="maxSpendUsdPerDay")
    can_delegate: bool | None = Field(default=None, alias="canDelegate")
    approval_rule_overrides: dict[str, str] = Field(default_factory=dict, alias="approvalRuleOverrides")

    model_config = {"populate_by_name": True}


class DelegationGrantCreate(BaseModel):
    grantor_agent_id: str | None = Field(default=None, alias="grantorAgentId")
    grantee_agent_id: str | None = Field(default=None, alias="granteeAgentId")
    grantee_user_id: str | None = Field(default=None, alias="granteeUserId")
    delegated_permissions: dict[str, Any] = Field(default_factory=dict, alias="delegatedPermissions")
    reason: str | None = None
    expires_in_minutes: int = Field(default=60, alias="expiresInMinutes", ge=1, le=60 * 24 * 30)

    model_config = {"populate_by_name": True}


def _client(settings: Settings):
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _assert_agent_in_org(client: Any, org_id: str, agent_id: str) -> None:
    rows = (
        client.table("agents")
        .select("id")
        .eq("org_id", org_id)
        .eq("id", agent_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")


@router.get("/{agent_id}/identity")
async def get_agent_identity(
    agent_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    _member: Annotated[tuple[str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization context required")
    client = _client(settings)
    aid = str(agent_id)
    _assert_agent_in_org(client, org_id, aid)
    status_payload = build_identity_status(client, org_id, aid)
    record = status_payload.get("record")
    return {
        "identity": serialize_identity_record(record) if record else None,
        "effective": status_payload.get("effective"),
        "usageToday": status_payload.get("usageToday"),
        "usageDate": status_payload.get("usageDate"),
    }


@router.put("/{agent_id}/identity")
async def put_agent_identity(
    agent_id: UUID,
    body: AgentIdentityUpsert,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization context required")
    client = _client(settings)
    aid = str(agent_id)
    _assert_agent_in_org(client, org_id, aid)
    row = upsert_agent_identity_record(
        client,
        org_id=org_id,
        agent_id=aid,
        actor_id=str(current_user["user_id"]),
        payload=body.model_dump(by_alias=True, exclude_none=True),
    )
    return {"identity": serialize_identity_record(row)}


@router.get("/{agent_id}/delegations")
async def get_agent_delegations(
    agent_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    _member: Annotated[tuple[str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization context required")
    client = _client(settings)
    aid = str(agent_id)
    _assert_agent_in_org(client, org_id, aid)
    grants = list_delegation_grants(client, org_id, agent_id=aid)
    return {"grants": grants}


@router.post("/{agent_id}/delegations")
async def post_agent_delegation(
    agent_id: UUID,
    body: DelegationGrantCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization context required")
    client = _client(settings)
    aid = str(agent_id)
    _assert_agent_in_org(client, org_id, aid)
    record = get_agent_identity_record(client, org_id, aid)
    if record and not record.get("can_delegate"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent is not configured to receive delegation grants",
        )
    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=body.expires_in_minutes)
    ).isoformat()
    grant = create_delegation_grant(
        client,
        org_id=org_id,
        actor_id=str(current_user["user_id"]),
        grantor_agent_id=body.grantor_agent_id,
        grantee_agent_id=str(body.grantee_agent_id or agent_id),
        grantee_user_id=body.grantee_user_id,
        delegated_permissions=body.delegated_permissions,
        reason=body.reason,
        expires_at=expires_at,
    )
    return {"grant": grant}


@router.delete("/{agent_id}/delegations/{grant_id}")
async def delete_agent_delegation(
    agent_id: UUID,
    grant_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    _admin: Annotated[None, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization context required")
    client = _client(settings)
    _assert_agent_in_org(client, org_id, str(agent_id))
    grant = revoke_delegation_grant(
        client,
        org_id=org_id,
        grant_id=str(grant_id),
        actor_id=str(current_user["user_id"]),
    )
    return {"grant": grant}
