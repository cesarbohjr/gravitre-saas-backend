"""B2B federation API — cross-org partnerships and handoffs (STA-116)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.core.errors import error_detail
from app.services.b2b_handoff_service import (
    B2BHandoffError,
    accept_cross_org_handoff,
    accept_partnership,
    complete_cross_org_handoff,
    create_cross_org_handoff,
    get_cross_org_handoff,
    invite_partner_org,
    list_cross_org_handoffs,
    list_partnerships,
    reject_cross_org_handoff,
    reject_partnership,
    revoke_partnership,
)

router = APIRouter(prefix="/api/federation", tags=["federation"])


class PartnershipInviteRequest(BaseModel):
    partner_org_id: str = Field(..., alias="partnerOrgId")

    model_config = {"populate_by_name": True}


class CrossOrgHandoffRequest(BaseModel):
    receiver_org_id: str = Field(..., alias="receiverOrgId")
    from_agent_id: str | None = Field(default=None, alias="fromAgentId")
    to_agent_id: str | None = Field(default=None, alias="toAgentId")
    briefing: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None
    source_output: dict[str, Any] | None = Field(default=None, alias="sourceOutput")
    message: str | None = None

    model_config = {"populate_by_name": True}


class HandoffRejectRequest(BaseModel):
    reason: str | None = None


def _client(settings: Settings):
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _raise_b2b(exc: B2BHandoffError) -> None:
    code_map = {
        "NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "FORBIDDEN": status.HTTP_403_FORBIDDEN,
        "CONFLICT": status.HTTP_409_CONFLICT,
        "PARTNERSHIP_REQUIRED": status.HTTP_409_CONFLICT,
        "VALIDATION_ERROR": status.HTTP_400_BAD_REQUEST,
    }
    raise HTTPException(
        status_code=code_map.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=error_detail(str(exc), exc.code),
    ) from exc


@router.get("/partnerships")
async def get_partnerships(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = _client(settings)
    return {"partnerships": list_partnerships(client, org_id)}


@router.post("/partnerships")
async def post_partnership_invite(
    body: PartnershipInviteRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        partnership = invite_partner_org(
            client,
            org_id=org_id,
            partner_org_id=body.partner_org_id,
            actor_id=user["user_id"],
        )
    except B2BHandoffError as exc:
        _raise_b2b(exc)
    return partnership


@router.post("/partnerships/{partnership_id}/accept")
async def post_partnership_accept(
    partnership_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return accept_partnership(
            client,
            org_id=org_id,
            partnership_id=partnership_id,
            actor_id=user["user_id"],
        )
    except B2BHandoffError as exc:
        _raise_b2b(exc)


@router.post("/partnerships/{partnership_id}/reject")
async def post_partnership_reject(
    partnership_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return reject_partnership(
            client,
            org_id=org_id,
            partnership_id=partnership_id,
            actor_id=user["user_id"],
        )
    except B2BHandoffError as exc:
        _raise_b2b(exc)


@router.post("/partnerships/{partnership_id}/revoke")
async def post_partnership_revoke(
    partnership_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return revoke_partnership(
            client,
            org_id=org_id,
            partnership_id=partnership_id,
            actor_id=user["user_id"],
        )
    except B2BHandoffError as exc:
        _raise_b2b(exc)


@router.get("/handoffs")
async def get_handoffs(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    direction: str = Query(default="all", pattern="^(all|inbound|outbound)$"),
    status_filter: str | None = Query(default=None, alias="status"),
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = _client(settings)
    return {
        "handoffs": list_cross_org_handoffs(
            client,
            org_id,
            direction=direction,
            status=status_filter,
        )
    }


@router.get("/handoffs/{handoff_id}")
async def get_handoff(
    handoff_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = _client(settings)
    try:
        return get_cross_org_handoff(client, org_id, handoff_id)
    except B2BHandoffError as exc:
        _raise_b2b(exc)


@router.post("/handoffs")
async def post_handoff(
    body: CrossOrgHandoffRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return create_cross_org_handoff(
            client,
            sender_org_id=org_id,
            receiver_org_id=body.receiver_org_id,
            from_agent_id=body.from_agent_id,
            to_agent_id=body.to_agent_id,
            briefing=body.briefing,
            parameters=body.parameters,
            source_output=body.source_output,
            message=body.message,
            sender_user_id=user["user_id"],
        )
    except B2BHandoffError as exc:
        _raise_b2b(exc)


@router.post("/handoffs/{handoff_id}/accept")
async def post_handoff_accept(
    handoff_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return accept_cross_org_handoff(
            client,
            org_id=org_id,
            handoff_id=handoff_id,
            actor_id=user["user_id"],
        )
    except B2BHandoffError as exc:
        _raise_b2b(exc)


@router.post("/handoffs/{handoff_id}/reject")
async def post_handoff_reject(
    handoff_id: str,
    body: HandoffRejectRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return reject_cross_org_handoff(
            client,
            org_id=org_id,
            handoff_id=handoff_id,
            actor_id=user["user_id"],
            reason=body.reason,
        )
    except B2BHandoffError as exc:
        _raise_b2b(exc)


@router.post("/handoffs/{handoff_id}/complete")
async def post_handoff_complete(
    handoff_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return complete_cross_org_handoff(
            client,
            org_id=org_id,
            handoff_id=handoff_id,
            actor_id=user["user_id"],
        )
    except B2BHandoffError as exc:
        _raise_b2b(exc)
