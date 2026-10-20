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

from app.auth.dependencies import require_admin
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
    # Legacy plaintext secret (read for compatibility; new secrets are encrypted).
    secret: str | None = None
    secret_encrypted: str | None = None
    secret_rotated_at: str | None = None
    allowed_ips: list[str] | None = None
    rate_limit_per_minute: int = 60
    # Admin who last configured the trigger; runs are attributed to them.
    configured_by: str | None = None


EVENT_ID_HEADER = "X-Gravitre-Event-Id"
_EVENT_ID_MAX = 200


def _signing_secret(config: WebhookConfig, settings: Settings) -> str | None:
    """Plaintext signing secret, decrypting the stored copy when encrypted."""
    if config.secret_encrypted:
        from app.connectors.crypto import decrypt_secret

        key = str(getattr(settings, "connector_secrets_encryption_key", "") or "")
        if not key:
            return None
        try:
            return decrypt_secret(config.secret_encrypted, key)
        except ValueError:
            return None
    return config.secret or None


def _client_ip(request: Request, settings: Settings) -> str | None:
    """Caller IP. X-Forwarded-For is trusted only for the configured proxy hops.

    The leftmost X-Forwarded-For entry is whatever the caller sent, so it was
    spoofable. With WEBHOOK_TRUSTED_PROXY_HOPS=N, the N-th entry from the right
    (appended by our own edge proxies) is used; with 0 only the socket peer.
    """
    hops = int(getattr(settings, "webhook_trusted_proxy_hops", 0) or 0)
    peer = request.client.host if request.client else None
    if hops <= 0:
        return peer
    chain = [p.strip() for p in (request.headers.get("x-forwarded-for") or "").split(",") if p.strip()]
    if len(chain) < hops:
        return peer
    return chain[-hops]


def verify_signature(
    payload: bytes,
    signature: str | None,
    secret: str,
    timestamp: str | None = None,
    max_age_seconds: int = 300,
    *,
    require_timestamp: bool = False,
) -> bool:
    if not signature:
        return False
    if require_timestamp and not timestamp:
        # Without a signed timestamp a captured request could be replayed forever.
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
        .select("id,name,org_id,status,definition,webhook_config,created_by")
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


def _resolve_triggered_by(
    settings: Settings, org_id: str, workflow: dict[str, Any], config: WebhookConfig
) -> str:
    from app.services.automation_actor import resolve_automation_actor

    actor = resolve_automation_actor(
        get_supabase_client(settings),
        org_id,
        configured_by=config.configured_by,
        workflow_created_by=workflow.get("created_by"),
    )
    if not actor:
        raise HTTPException(status_code=409, detail="No accountable organization member to attribute this run to")
    return actor


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

    # Fail closed: an unsigned trigger used to run whenever no secret was set, and
    # a signature without a timestamp could be replayed indefinitely.
    secret = _signing_secret(webhook_config, settings)
    if not secret:
        logger.warning("webhook_secret_missing workflow_id=%s", workflow_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook signing secret is not configured for this workflow",
        )
    if not verify_signature(
        payload=body,
        signature=x_gravitre_signature,
        secret=secret,
        timestamp=x_gravitre_timestamp,
        require_timestamp=True,
    ):
        logger.warning("webhook_signature_invalid workflow_id=%s", workflow_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    event_id = (request.headers.get(EVENT_ID_HEADER) or "").strip()
    if not event_id or len(event_id) > _EVENT_ID_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{EVENT_ID_HEADER} header is required (at most {_EVENT_ID_MAX} characters)",
        )

    if webhook_config.allowed_ips:
        client_ip = _client_ip(request, settings)
        if client_ip not in webhook_config.allowed_ips:
            logger.warning("webhook_ip_blocked workflow_id=%s client_ip=%s", workflow_id, client_ip)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="IP not allowed")

    try:
        payload = json.loads(body.decode("utf-8")) if body else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload") from exc

    org_id = str(workflow["org_id"])
    triggered_by = _resolve_triggered_by(settings, org_id, workflow, webhook_config)
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
        provider_event_id=event_id,
    )
    run_status = str(outcome.get("status") or "")
    if run_status == "failed" and outcome.get("retryable"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Try again shortly")
    if run_status == "failed":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Workflow execution failed")
    if run_status == "skipped" and outcome.get("reason") == "duplicate_event":
        # A replay or provider retry of an event already handled: acknowledge it.
        return WebhookTriggerResponse(
            run_id="",
            workflow_id=workflow_id,
            status="duplicate",
            message="Event already received; no second run was started",
        )
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


def _require_workflow_admin(workflow: dict[str, Any], admin: tuple) -> None:
    _user, admin_org = admin
    if str(workflow.get("org_id")) != str(admin_org):
        raise HTTPException(status_code=404, detail="Workflow not found")


def _load_workflow_row(workflow_id: str, settings: Settings) -> dict[str, Any]:
    client = get_supabase_client(settings)
    result = (
        client.table("workflow_defs")
        .select("id,name,org_id,status,webhook_config")
        .eq("id", workflow_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return dict(result.data[0])


def _config_view(workflow_id: str, config: WebhookConfig) -> dict[str, Any]:
    return {
        "enabled": config.enabled,
        "has_secret": bool(config.secret_encrypted or config.secret),
        "secret_rotated_at": config.secret_rotated_at,
        "allowed_ips": config.allowed_ips,
        "rate_limit_per_minute": config.rate_limit_per_minute,
        "url": f"/api/webhooks/triggers/{workflow_id}",
        "signing": {
            "algorithm": "HMAC-SHA256",
            "signature_header": "X-Gravitre-Signature",
            "timestamp_header": "X-Gravitre-Timestamp",
            "event_id_header": EVENT_ID_HEADER,
            "signed_content": "<timestamp>.<raw body>",
            "max_age_seconds": 300,
        },
    }


@router.get("/{workflow_id}/config")
def get_webhook_config(
    workflow_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Org admins only (it used to answer anyone who knew a workflow id)."""
    workflow = _load_workflow_row(workflow_id, settings)
    _require_workflow_admin(workflow, admin)
    return _config_view(workflow_id, WebhookConfig.model_validate(workflow.get("webhook_config") or {}))


class WebhookConfigUpdate(BaseModel):
    enabled: bool | None = None
    allowed_ips: list[str] | None = None
    rate_limit_per_minute: int | None = None
    rotate_secret: bool = False


@router.put("/{workflow_id}/config")
def update_webhook_config(
    workflow_id: str,
    body: WebhookConfigUpdate,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Configure the signed trigger. A new secret is returned once, stored encrypted.

    Enabling requires a secret: the first enable generates one.
    """
    import secrets as _secrets

    from app.connectors.crypto import encrypt_secret
    from app.workflows.audit import write_audit_event

    workflow = _load_workflow_row(workflow_id, settings)
    _require_workflow_admin(workflow, admin)
    config = WebhookConfig.model_validate(workflow.get("webhook_config") or {})
    data = config.model_dump()
    if body.enabled is not None:
        data["enabled"] = bool(body.enabled)
    if body.allowed_ips is not None:
        data["allowed_ips"] = [ip.strip() for ip in body.allowed_ips if ip and ip.strip()] or None
    if body.rate_limit_per_minute is not None:
        data["rate_limit_per_minute"] = max(1, min(int(body.rate_limit_per_minute), 6000))

    new_secret: str | None = None
    needs_secret = data["enabled"] and not (data.get("secret_encrypted") or data.get("secret"))
    if body.rotate_secret or needs_secret:
        key = str(getattr(settings, "connector_secrets_encryption_key", "") or "")
        if not key:
            raise HTTPException(status_code=400, detail="CONNECTOR_SECRETS_ENCRYPTION_KEY required to store a signing secret")
        new_secret = "whsec_" + _secrets.token_urlsafe(32)
        data["secret_encrypted"] = encrypt_secret(new_secret, key)
        data["secret"] = None
        data["secret_rotated_at"] = datetime.now(timezone.utc).isoformat()

    user, org_id = admin
    data["configured_by"] = str(user.get("user_id") or "") or None
    client = get_supabase_client(settings)
    client.table("workflow_defs").update({"webhook_config": data}).eq("id", workflow_id).eq(
        "org_id", str(workflow["org_id"])
    ).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=str(user.get("user_id") or ""),
        action="workflow.webhook_config.updated",
        resource_type="workflow",
        resource_id=workflow_id,
        metadata={
            "enabled": data["enabled"],
            "secret_rotated": bool(new_secret),
            "allowed_ips": data.get("allowed_ips"),
        },
    )
    view = _config_view(workflow_id, WebhookConfig.model_validate(data))
    if new_secret:
        view["secret"] = new_secret  # shown once; only the encrypted copy is stored
    return view
