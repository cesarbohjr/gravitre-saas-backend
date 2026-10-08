from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.middleware.entitlements import resolve_entitlements
from app.services.execution_service import ExecutionService, get_execution_service
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)
router = APIRouter(prefix="/api/webhooks/triggers", tags=["webhook-triggers"])


class WebhookTriggerResponse(BaseModel):
    run_id: str
    workflow_id: str
    status: str
    message: str


class WebhookConfig(BaseModel):
    enabled: bool = False
    secret: str | None = None
    allowed_ips: list[str] | None = None
    rate_limit_per_minute: int = 60


def verify_signature(
    payload: bytes,
    signature: str | None,
    secret: str,
    timestamp: str | None = None,
    max_age_seconds: int = 300,
) -> bool:
    if not signature:
        return False
    if timestamp:
        try:
            ts = int(timestamp)
        except ValueError:
            return False
        if abs(time.time() - ts) > max_age_seconds:
            return False
        sign_base = timestamp.encode("utf-8") + b"." + payload
    else:
        sign_base = payload
    expected = hmac.new(secret.encode("utf-8"), sign_base, hashlib.sha256).hexdigest()
    actual = signature.replace("sha256=", "")
    return hmac.compare_digest(expected, actual)


def _get_workflow_webhook_config(workflow_id: str, settings: Settings) -> tuple[dict[str, Any], WebhookConfig]:
    client = get_supabase_client(settings)
    result = (
        client.table("workflow_defs")
        .select("id,name,org_id,status,definition,webhook_config")
        .eq("id", workflow_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Workflow not found")
    workflow = dict(result.data[0])
    if (workflow.get("status") or "draft") != "active":
        raise HTTPException(status_code=400, detail="Workflow is not active")
    webhook_config = WebhookConfig.model_validate(workflow.get("webhook_config") or {})
    if not webhook_config.enabled:
        raise HTTPException(status_code=400, detail="Webhook trigger not enabled for this workflow")

    entitlements = resolve_entitlements(settings, str(workflow["org_id"]))
    features = entitlements.get("features") or {}
    if not bool(features.get("custom_webhooks")):
        raise HTTPException(status_code=403, detail="Custom webhooks feature is not enabled for this organization")
    return workflow, webhook_config


def _resolve_triggered_by(settings: Settings, org_id: str) -> str:
    client = get_supabase_client(settings)
    membership = (
        client.table("organization_members")
        .select("user_id,role")
        .eq("org_id", org_id)
        .in_("role", ["owner", "admin", "member"])
        .limit(1)
        .execute()
    )
    if not membership.data:
        raise HTTPException(status_code=400, detail="No organization member available to attribute webhook run")
    return str(membership.data[0]["user_id"])


@router.post("/{workflow_id}", response_model=WebhookTriggerResponse)
async def trigger_workflow(
    workflow_id: str,
    request: Request,
    x_gravitre_signature: Annotated[str | None, Header()] = None,
    x_gravitre_timestamp: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
    execution_service: ExecutionService = Depends(get_execution_service),
) -> WebhookTriggerResponse:
    workflow, webhook_config = _get_workflow_webhook_config(workflow_id, settings)
    body = await request.body()

    if webhook_config.secret and not verify_signature(
        payload=body,
        signature=x_gravitre_signature,
        secret=webhook_config.secret,
        timestamp=x_gravitre_timestamp,
    ):
        logger.warning("webhook_signature_invalid workflow_id=%s", workflow_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    if webhook_config.allowed_ips:
        client_ip = request.client.host if request.client else None
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        if client_ip not in webhook_config.allowed_ips:
            logger.warning("webhook_ip_blocked workflow_id=%s client_ip=%s", workflow_id, client_ip)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="IP not allowed")

    try:
        payload = json.loads(body.decode("utf-8")) if body else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload") from exc

    org_id = str(workflow["org_id"])
    triggered_by = _resolve_triggered_by(settings, org_id)
    definition = workflow.get("definition") or {"schema_version": "v1", "steps": []}
    parameters = payload if isinstance(payload, dict) else {"payload": payload}
    client = get_supabase_client(settings)
    from app.services.event_triggered_runs import start_event_triggered_run

    # Same policy and approval floor as a manual run: a workflow with writes
    # waits for approval instead of failing at the canvas write gate.
    outcome = await start_event_triggered_run(
        settings,
        client,
        org_id=org_id,
        workflow_id=workflow_id,
        definition=definition,
        parameters=parameters,
        actor_id=triggered_by,
        trigger_type="webhook",
        source="webhook_trigger",
        execution_service=execution_service,
    )
    run_status = str(outcome.get("status") or "")
    if run_status == "failed":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Workflow execution failed")
    if run_status == "blocked":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(outcome.get("reason") or "Policy denied"))
    if run_status == "skipped":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(outcome.get("reason") or "Run not started"))
    message = (
        "Workflow is waiting for approval before it runs"
        if run_status == "pending_approval"
        else "Workflow triggered successfully"
    )
    return WebhookTriggerResponse(
        run_id=str(outcome.get("run_id") or ""),
        workflow_id=workflow_id,
        status=run_status,
        message=message,
    )


@router.get("/{workflow_id}/config")
def get_webhook_config(
    workflow_id: str,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _workflow, webhook_config = _get_workflow_webhook_config(workflow_id, settings)
    return {
        "enabled": webhook_config.enabled,
        "has_secret": webhook_config.secret is not None,
        "allowed_ips": webhook_config.allowed_ips,
        "rate_limit_per_minute": webhook_config.rate_limit_per_minute,
        "url": f"/api/webhooks/triggers/{workflow_id}",
    }
