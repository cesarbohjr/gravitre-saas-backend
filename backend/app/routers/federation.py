"""B2B federation API — partnerships, handoffs, grants, delegated tasks (STA-116–118)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.core.errors import error_detail
from app.core.logging import get_logger
from app.middleware.entitlements import require_feature
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
from app.services.cross_org_delegated_task_service import (
    DelegatedTaskError,
    accept_delegated_task,
    cancel_delegated_task,
    complete_delegated_task,
    delegate_task_to_partner,
    fail_delegated_task,
    get_delegated_task,
    list_delegated_tasks,
    reject_delegated_task,
    start_delegated_task,
)
from app.services.federated_connector_service import (
    FederatedConnectorError,
    accept_federated_grant,
    get_federated_grant,
    list_federated_grants,
    propose_federated_grant,
    reject_federated_grant,
    revoke_federated_grant,
)

router = APIRouter(
    prefix="/api/federation",
    tags=["federation"],
    dependencies=[Depends(require_feature("api_full_access"))],
)
logger = get_logger(__name__)


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


class FederatedGrantRequest(BaseModel):
    grantee_org_id: str = Field(..., alias="granteeOrgId")
    connector_id: str = Field(..., alias="connectorId")
    allowed_actions: list[str] = Field(..., alias="allowedActions", min_length=1)
    label: str | None = None
    expires_in_hours: int = Field(default=24, alias="expiresInHours", ge=1, le=168)

    model_config = {"populate_by_name": True}


class DelegatedTaskRequest(BaseModel):
    delegate_org_id: str = Field(..., alias="delegateOrgId")
    title: str = Field(..., min_length=1)
    instructions: str | None = None
    payload: dict[str, Any] | None = None
    parent_reference: dict[str, Any] | None = Field(default=None, alias="parentReference")
    delegator_agent_id: str | None = Field(default=None, alias="delegatorAgentId")
    delegate_agent_id: str | None = Field(default=None, alias="delegateAgentId")

    model_config = {"populate_by_name": True}


class DelegatedTaskAcceptRequest(BaseModel):
    delegate_agent_id: str | None = Field(default=None, alias="delegateAgentId")
    spawn_agent_job: bool = Field(default=False, alias="spawnAgentJob")

    model_config = {"populate_by_name": True}


class DelegatedTaskCompleteRequest(BaseModel):
    result: dict[str, Any] | None = None


class DelegatedTaskReasonRequest(BaseModel):
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


def _raise_federated(exc: FederatedConnectorError) -> None:
    _raise_b2b(exc)


def _raise_delegated(exc: DelegatedTaskError) -> None:
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
    if not settings.supabase_service_role_key:
        logger.warning("federation_partnerships_missing_service_role org_id=%s", org_id)
        return {"partnerships": []}
    client = _client(settings)
    try:
        return {"partnerships": list_partnerships(client, org_id)}
    except Exception as exc:
        logger.exception("federation_partnerships_failed org_id=%s error=%s", org_id, exc)
        return {"partnerships": []}


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
    return {"partnership": partnership}


@router.post("/partnerships/{partnership_id}/accept")
async def post_partnership_accept(
    partnership_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        partnership = accept_partnership(
            client,
            org_id=org_id,
            partnership_id=partnership_id,
            actor_id=user["user_id"],
        )
    except B2BHandoffError as exc:
        _raise_b2b(exc)
    return {"partnership": partnership}


@router.post("/partnerships/{partnership_id}/reject")
async def post_partnership_reject(
    partnership_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        partnership = reject_partnership(
            client,
            org_id=org_id,
            partnership_id=partnership_id,
            actor_id=user["user_id"],
        )
    except B2BHandoffError as exc:
        _raise_b2b(exc)
    return {"partnership": partnership}


@router.post("/partnerships/{partnership_id}/revoke")
async def post_partnership_revoke(
    partnership_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        partnership = revoke_partnership(
            client,
            org_id=org_id,
            partnership_id=partnership_id,
            actor_id=user["user_id"],
        )
    except B2BHandoffError as exc:
        _raise_b2b(exc)
    return {"partnership": partnership}


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
    if not settings.supabase_service_role_key:
        logger.warning("federation_handoffs_missing_service_role org_id=%s", org_id)
        return {"handoffs": []}
    client = _client(settings)
    try:
        return {
            "handoffs": list_cross_org_handoffs(
                client,
                org_id,
                direction=direction,
                status=status_filter,
            )
        }
    except Exception as exc:
        logger.exception("federation_handoffs_failed org_id=%s error=%s", org_id, exc)
        return {"handoffs": []}


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
        handoff = create_cross_org_handoff(
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
    return {"handoff": handoff}


@router.post("/handoffs/{handoff_id}/accept")
async def post_handoff_accept(
    handoff_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        handoff = accept_cross_org_handoff(
            client,
            org_id=org_id,
            handoff_id=handoff_id,
            actor_id=user["user_id"],
        )
    except B2BHandoffError as exc:
        _raise_b2b(exc)
    return {"handoff": handoff}


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
        handoff = reject_cross_org_handoff(
            client,
            org_id=org_id,
            handoff_id=handoff_id,
            actor_id=user["user_id"],
            reason=body.reason,
        )
    except B2BHandoffError as exc:
        _raise_b2b(exc)
    return {"handoff": handoff}


@router.post("/handoffs/{handoff_id}/complete")
async def post_handoff_complete(
    handoff_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        handoff = complete_cross_org_handoff(
            client,
            org_id=org_id,
            handoff_id=handoff_id,
            actor_id=user["user_id"],
        )
    except B2BHandoffError as exc:
        _raise_b2b(exc)
    return {"handoff": handoff}


@router.get("/connector-grants")
async def get_connector_grants(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = _client(settings)
    return {"grants": list_federated_grants(client, org_id)}


@router.get("/connector-grants/{grant_id}")
async def get_connector_grant(
    grant_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = _client(settings)
    try:
        return get_federated_grant(client, org_id, grant_id)
    except FederatedConnectorError as exc:
        _raise_federated(exc)


@router.post("/connector-grants")
async def post_connector_grant(
    body: FederatedGrantRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return propose_federated_grant(
            client,
            grantor_org_id=org_id,
            grantee_org_id=body.grantee_org_id,
            connector_id=body.connector_id,
            allowed_actions=body.allowed_actions,
            actor_id=user["user_id"],
            label=body.label,
            expires_in_hours=body.expires_in_hours,
        )
    except FederatedConnectorError as exc:
        _raise_federated(exc)


@router.post("/connector-grants/{grant_id}/accept")
async def post_connector_grant_accept(
    grant_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return accept_federated_grant(
            client,
            org_id=org_id,
            grant_id=grant_id,
            actor_id=user["user_id"],
        )
    except FederatedConnectorError as exc:
        _raise_federated(exc)


@router.post("/connector-grants/{grant_id}/reject")
async def post_connector_grant_reject(
    grant_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return reject_federated_grant(
            client,
            org_id=org_id,
            grant_id=grant_id,
            actor_id=user["user_id"],
        )
    except FederatedConnectorError as exc:
        _raise_federated(exc)


@router.post("/connector-grants/{grant_id}/revoke")
async def post_connector_grant_revoke(
    grant_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return revoke_federated_grant(
            client,
            org_id=org_id,
            grant_id=grant_id,
            actor_id=user["user_id"],
        )
    except FederatedConnectorError as exc:
        _raise_federated(exc)


@router.get("/delegated-tasks")
async def get_delegated_tasks(
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
        "tasks": list_delegated_tasks(
            client,
            org_id,
            direction=direction,
            status=status_filter,
        )
    }


@router.get("/delegated-tasks/{task_id}")
async def get_delegated_task_route(
    task_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = _client(settings)
    try:
        return get_delegated_task(client, org_id, task_id)
    except DelegatedTaskError as exc:
        _raise_delegated(exc)


@router.post("/delegated-tasks")
async def post_delegated_task(
    body: DelegatedTaskRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return delegate_task_to_partner(
            client,
            delegator_org_id=org_id,
            delegate_org_id=body.delegate_org_id,
            title=body.title,
            delegator_user_id=user["user_id"],
            instructions=body.instructions,
            payload=body.payload,
            parent_reference=body.parent_reference,
            delegator_agent_id=body.delegator_agent_id,
            delegate_agent_id=body.delegate_agent_id,
        )
    except DelegatedTaskError as exc:
        _raise_delegated(exc)


@router.post("/delegated-tasks/{task_id}/accept")
async def post_delegated_task_accept(
    task_id: str,
    body: DelegatedTaskAcceptRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return accept_delegated_task(
            client,
            org_id=org_id,
            task_id=task_id,
            actor_id=user["user_id"],
            delegate_agent_id=body.delegate_agent_id,
            spawn_agent_job=body.spawn_agent_job,
        )
    except DelegatedTaskError as exc:
        _raise_delegated(exc)


@router.post("/delegated-tasks/{task_id}/reject")
async def post_delegated_task_reject(
    task_id: str,
    body: DelegatedTaskReasonRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return reject_delegated_task(
            client,
            org_id=org_id,
            task_id=task_id,
            actor_id=user["user_id"],
            reason=body.reason,
        )
    except DelegatedTaskError as exc:
        _raise_delegated(exc)


@router.post("/delegated-tasks/{task_id}/start")
async def post_delegated_task_start(
    task_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return start_delegated_task(
            client,
            org_id=org_id,
            task_id=task_id,
            actor_id=user["user_id"],
        )
    except DelegatedTaskError as exc:
        _raise_delegated(exc)


@router.post("/delegated-tasks/{task_id}/complete")
async def post_delegated_task_complete(
    task_id: str,
    body: DelegatedTaskCompleteRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return complete_delegated_task(
            client,
            org_id=org_id,
            task_id=task_id,
            actor_id=user["user_id"],
            result=body.result,
        )
    except DelegatedTaskError as exc:
        _raise_delegated(exc)


@router.post("/delegated-tasks/{task_id}/fail")
async def post_delegated_task_fail(
    task_id: str,
    body: DelegatedTaskReasonRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return fail_delegated_task(
            client,
            org_id=org_id,
            task_id=task_id,
            actor_id=user["user_id"],
            reason=body.reason,
        )
    except DelegatedTaskError as exc:
        _raise_delegated(exc)


@router.post("/delegated-tasks/{task_id}/cancel")
async def post_delegated_task_cancel(
    task_id: str,
    body: DelegatedTaskReasonRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = _client(settings)
    try:
        return cancel_delegated_task(
            client,
            org_id=org_id,
            task_id=task_id,
            actor_id=user["user_id"],
            reason=body.reason,
        )
    except DelegatedTaskError as exc:
        _raise_delegated(exc)
