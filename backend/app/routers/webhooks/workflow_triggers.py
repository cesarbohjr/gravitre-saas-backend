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
from app.workflows.repository import create_execute_run, get_supabase_client
from app.workflows.schema import compute_run_hash

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
    run_id = str(uuid.uuid4())
    triggered_by = _resolve_triggered_by(settings, org_id)
    definition = workflow.get("definition") or {"schema_version": "v1", "steps": []}
    parameters = payload if isinstance(payload, dict) else {"payload": payload}
    run_hash = compute_run_hash(definition, parameters, str(definition.get("schema_version") or "v1"))

    client = get_supabase_client(settings)
    created_run = create_execute_run(
        client=client,
        org_id=org_id,
        workflow_id=workflow_id,
        triggered_by=triggered_by,
        definition_snapshot=definition,
        parameters=parameters,
        run_hash=run_hash,
        status="running",
        approval_status="approved",
        required_approvals=0,
        approver_roles=[],
        environment_name="production",
        trigger_type="webhook",
    )
    run_id = str(created_run["id"])

    try:
        result = await execution_service.execute_workflow(
            org_id=org_id,
            workflow_id=workflow_id,
            run_id=run_id,
            parameters=parameters,
        )
        update_payload: dict[str, Any] = {"status": result.status}
        if result.status == "failed":
            failed_step = next((item for item in result.results if item.status == "failed"), None)
            update_payload["error_message"] = failed_step.error if failed_step else "Execution failed"
        if result.status in {"completed", "failed", "cancelled"}:
            update_payload["completed_at"] = datetime.now(timezone.utc).isoformat()
        client.table("workflow_runs").update(update_payload).eq("id", run_id).execute()
        return WebhookTriggerResponse(
            run_id=run_id,
            workflow_id=workflow_id,
            status=result.status,
            message="Workflow triggered successfully",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("webhook_execution_error workflow_id=%s run_id=%s error=%s", workflow_id, run_id, str(exc))
        client.table("workflow_runs").update(
            {
                "status": "failed",
                "error_message": str(exc),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", run_id).execute()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Workflow execution failed") from exc


@router.get("/{workflow_id}/config")
async def get_webhook_config(
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
