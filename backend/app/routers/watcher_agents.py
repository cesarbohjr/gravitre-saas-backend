"""Free-form watcher → agent_jobs API (/api/watchers/agent)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.watcher_agent_adapter import (
    WatcherAgentError,
    get_watcher_agent_adapter,
)
from app.routers.webhooks.workflow_triggers import verify_signature

router = APIRouter(prefix="/api/watchers", tags=["watcher-agents"])


class WatcherAgentRequest(BaseModel):
    objective: str = Field(..., min_length=1)
    source: str = Field(default="webhook", pattern="^(webhook|cron|external_signal)$")
    agent_id: str | None = Field(default=None, alias="agentId")
    proposed_action: str | None = Field(default=None, alias="proposedAction")
    approval_granted: bool = Field(default=False, alias="approvalGranted")
    metadata: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


def _raise(exc: WatcherAgentError) -> None:
    code_map = {
        "VALIDATION_ERROR": status.HTTP_400_BAD_REQUEST,
        "WRITE_AUTHORITY_DENIED": status.HTTP_403_FORBIDDEN,
    }
    raise HTTPException(
        status_code=code_map.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=str(exc),
    ) from exc


@router.post("/agent")
async def create_watcher_agent_job(
    body: WatcherAgentRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Admin/authenticated path: enqueue a watcher-triggered agent job."""
    user, org_id = admin
    actor_id = str(user.get("user_id") or user.get("id") or "") or None
    try:
        return await get_watcher_agent_adapter(settings).enqueue_from_watcher(
            org_id,
            objective=body.objective,
            source=body.source,
            agent_id=body.agent_id,
            created_by=actor_id,
            proposed_action=body.proposed_action,
            approval_granted=body.approval_granted,
            metadata=body.metadata,
        )
    except WatcherAgentError as exc:
        _raise(exc)


@router.post("/agent/signal")
async def create_watcher_agent_job_from_signal(
    body: WatcherAgentRequest,
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_gravitre_signature: Annotated[str | None, Header(alias="X-Gravitre-Signature")] = None,
    x_gravitre_timestamp: Annotated[str | None, Header(alias="X-Gravitre-Timestamp")] = None,
    x_watcher_secret: Annotated[str | None, Header(alias="X-Watcher-Secret")] = None,
) -> dict[str, Any]:
    """External webhook/cron/signal path with shared-secret or HMAC verification.

    Requires org context (API key / session) plus optional HMAC when
    WATCHER_AGENT_WEBHOOK_SECRET is configured.
    """
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")

    secret = (getattr(settings, "watcher_agent_webhook_secret", None) or "").strip()
    if secret:
        raw = body.model_dump_json().encode("utf-8")
        ok = False
        if x_gravitre_signature:
            ok = verify_signature(raw, x_gravitre_signature, secret, x_gravitre_timestamp)
        if not ok and x_watcher_secret and x_watcher_secret == secret:
            ok = True
        if not ok:
            raise HTTPException(status_code=401, detail="Invalid watcher signature")

    try:
        return await get_watcher_agent_adapter(settings).enqueue_from_watcher(
            org_id,
            objective=body.objective,
            source=body.source,
            agent_id=body.agent_id,
            proposed_action=body.proposed_action,
            approval_granted=body.approval_granted,
            metadata=body.metadata,
        )
    except WatcherAgentError as exc:
        _raise(exc)
