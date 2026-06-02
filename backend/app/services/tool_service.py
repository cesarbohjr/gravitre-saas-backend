"""Unified tool invocation for agents and workflows (STA-10)."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from app.config import Settings
from app.connectors.email import body_hash as _body_hash
from app.connectors.email import extract_to_domain
from app.connectors.email import send_email_smtp
from app.connectors.email import subject_hash as _subject_hash
from app.connectors.rate_limit import RateLimitError, enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret
from app.connectors.slack import message_hash, send_slack_message
from app.connectors.webhook import (
    ALLOWED_HEADER_NAMES as WEBHOOK_ALLOWED_HEADERS,
    build_headers,
    build_url,
    coerce_payload,
    parse_connector_config,
    payload_hash as _payload_hash,
    resolve_and_validate_host,
    sanitize_headers,
    send_webhook,
    validate_path,
)
from app.connectors.crypto import decrypt_secret
from app.connectors.hubspot import (
    HubSpotAPIError,
    add_contact_to_list,
    create_contact,
    create_deal,
    create_note,
    enroll_contact_in_sequence,
    get_contact,
    get_deal,
    search_contacts,
    update_contact,
    update_deal,
    update_deal_stage,
)
from app.connectors.hubspot_oauth import ensure_hubspot_access_token
from app.services.agent_tool_permissions import assert_agent_tool_permission
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolError,
    ToolNotFoundError,
    ToolPermissionDeniedError,
    ToolRateLimitedError,
    ToolValidationError,
)
from app.workflows.audit import write_audit_event
from app.workflows.constants import RESOURCE_TYPE_WORKFLOW_RUN

ToolExecutor = Callable[[ToolContext, dict[str, Any]], NormalizedResult]

_MAX_RETRIES = 2
_RETRY_BACKOFF_SEC = (0.5, 1.0)

_AUTH_HINTS = ("unauthorized", "invalid_auth", "token", "expired", "authentication", "401", "403")


def _classify_error(exc: Exception) -> ToolError:
    if isinstance(exc, ToolError):
        return exc
    if isinstance(exc, RateLimitError):
        return ToolRateLimitedError(str(exc))
    msg = str(exc).lower()
    if any(h in msg for h in _AUTH_HINTS):
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _audit_resource_id(ctx: ToolContext) -> str:
    if ctx.task_id:
        return ctx.task_id
    if ctx.run_id:
        return ctx.run_id
    return ctx.org_id


def _audit_resource_type(ctx: ToolContext) -> str:
    if ctx.task_id or ctx.agent_id:
        return "agent_task"
    return RESOURCE_TYPE_WORKFLOW_RUN


def _audit_metadata(ctx: ToolContext, action: str, connector_id: str | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "action": action,
        "connector_id": connector_id,
        "step_id": ctx.step_id,
    }
    if ctx.agent_id:
        meta["agent_id"] = ctx.agent_id
    if ctx.task_id:
        meta["task_id"] = ctx.task_id
    if ctx.run_id:
        meta["run_id"] = ctx.run_id
    if extra:
        meta.update(extra)
    return meta


def _write_tool_audit(
    ctx: ToolContext,
    action: str,
    connector_id: str | None,
    audit_action: str,
    extra: dict[str, Any] | None = None,
) -> None:
    write_audit_event(
        ctx.client,
        ctx.org_id,
        ctx.actor_id,
        action=audit_action,
        resource_type=_audit_resource_type(ctx),
        resource_id=_audit_resource_id(ctx),
        metadata=_audit_metadata(ctx, action, connector_id, extra),
    )


def _enforce_tool_rate_limit(
    ctx: ToolContext,
    connector_type: str,
    connector_id: str,
) -> None:
    step_type = ctx.step_type or connector_type
    enforce_rate_limit(ctx.client, ctx.org_id, step_type, connector_type, connector_id)


def _hubspot_connector_and_token(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, "hubspot", environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("No active HubSpot connector found for org")
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "hubspot", cid)
    token, err = ensure_hubspot_access_token(
        ctx.client,
        ctx.org_id,
        cid,
        ctx.settings,
        environment_name=conn.get("environment") or ctx.environment_name,
    )
    if err or not token:
        raise ToolAuthExpiredError(err or "HubSpot OAuth not connected")
    return cid, token


def _handle_hubspot_error(exc: HubSpotAPIError) -> ToolError:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _exec_hubspot_contacts_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    try:
        data = get_contact(
            token,
            contact_id=params.get("contact_id") or params.get("contactId"),
            email=params.get("email"),
            properties=params.get("properties"),
        )
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.contacts.get",
        connector_id=cid,
        data={"contact": data},
    )


def _exec_hubspot_contacts_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    contact_id = params.get("contact_id") or params.get("contactId")
    properties = params.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise ToolValidationError("hubspot.contacts.update requires properties object")
    try:
        data = update_contact(token, str(contact_id), properties)
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.contacts.update",
        connector_id=cid,
        data={"contact": data},
    )


def _exec_hubspot_notes_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    body = str(params.get("body") or params.get("note") or "")
    try:
        data = create_note(
            token,
            body=body,
            contact_id=params.get("contact_id") or params.get("contactId"),
            deal_id=params.get("deal_id") or params.get("dealId"),
        )
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.notes.create",
        connector_id=cid,
        data={"note": data},
    )


def _exec_hubspot_deals_update_stage(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    deal_id = params.get("deal_id") or params.get("dealId")
    dealstage = params.get("dealstage") or params.get("stage")
    try:
        data = update_deal_stage(token, str(deal_id), str(dealstage))
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.deals.update_stage",
        connector_id=cid,
        data={"deal": data},
    )


def _exec_hubspot_contacts_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    properties = params.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise ToolValidationError("hubspot.contacts.create requires properties object")
    try:
        data = create_contact(token, properties)
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.contacts.create",
        connector_id=cid,
        data={"contact": data},
    )


def _exec_hubspot_contacts_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    filter_groups = params.get("filter_groups") or params.get("filterGroups")
    if not isinstance(filter_groups, list) or not filter_groups:
        raise ToolValidationError("hubspot.contacts.search requires filter_groups array")
    try:
        data = search_contacts(
            token,
            filter_groups=filter_groups,
            properties=params.get("properties"),
            limit=int(params.get("limit") or 10),
        )
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.contacts.search",
        connector_id=cid,
        data={"search": data},
    )


def _exec_hubspot_deals_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    deal_id = params.get("deal_id") or params.get("dealId")
    if not deal_id:
        raise ToolValidationError("hubspot.deals.get requires deal_id")
    try:
        data = get_deal(token, str(deal_id), properties=params.get("properties"))
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.deals.get",
        connector_id=cid,
        data={"deal": data},
    )


def _exec_hubspot_deals_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    properties = params.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise ToolValidationError("hubspot.deals.create requires properties object")
    try:
        data = create_deal(
            token,
            properties,
            contact_id=params.get("contact_id") or params.get("contactId"),
        )
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.deals.create",
        connector_id=cid,
        data={"deal": data},
    )


def _exec_hubspot_deals_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    deal_id = params.get("deal_id") or params.get("dealId")
    properties = params.get("properties")
    if not deal_id:
        raise ToolValidationError("hubspot.deals.update requires deal_id")
    if not isinstance(properties, dict) or not properties:
        raise ToolValidationError("hubspot.deals.update requires properties object")
    try:
        data = update_deal(token, str(deal_id), properties)
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.deals.update",
        connector_id=cid,
        data={"deal": data},
    )


def _exec_hubspot_lists_add_contact(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    list_id = params.get("list_id") or params.get("listId")
    contact_id = params.get("contact_id") or params.get("contactId")
    if not list_id or not contact_id:
        raise ToolValidationError("hubspot.lists.add_contact requires list_id and contact_id")
    try:
        data = add_contact_to_list(token, str(list_id), str(contact_id))
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.lists.add_contact",
        connector_id=cid,
        data={"membership": data},
    )


def _exec_hubspot_sequences_enroll(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _hubspot_connector_and_token(ctx, params)
    try:
        data = enroll_contact_in_sequence(
            token,
            contact_id=str(params.get("contact_id") or params.get("contactId")),
            sequence_id=str(params.get("sequence_id") or params.get("sequenceId")),
            sender_email=params.get("sender_email") or params.get("senderEmail"),
        )
    except HubSpotAPIError as exc:
        raise _handle_hubspot_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="hubspot.sequences.enroll",
        connector_id=cid,
        data={"enrollment": data},
    )


def _exec_slack_post_message(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, "slack", environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("No active Slack connector found for org")
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "slack", cid)
    token = get_decrypted_secret(ctx.client, cid, "token", ctx.settings)
    if not token:
        raise ToolAuthExpiredError("Slack connector missing token secret")
    channel = (params.get("channel") or "").strip()
    text = (params.get("message") or params.get("text") or "").strip()
    if not channel:
        raise ToolValidationError("Slack channel is required")
    if not text:
        raise ToolValidationError("Slack message is required")
    result = send_slack_message(token, channel, text)
    return NormalizedResult(
        success=True,
        action="slack.post_message",
        connector_id=cid,
        latency_ms=int(result.get("_latency_ms", 0) or 0),
        data={"executed": True, "channel": channel, "ts": result.get("ts"), "ok": True},
    )


def _exec_email_send(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    if not connector_id:
        raise ToolValidationError("email.send requires connector_id")
    conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("Connector not found")
    if conn.get("type") != "email":
        raise ToolValidationError("Connector must be type email")
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "email", cid)
    to_addr = (params.get("to") or "").strip()
    subject = str(params.get("subject") or "")
    body = str(params.get("body") or "")
    if not to_addr:
        raise ToolValidationError("email.send requires to")
    content_type = (params.get("content_type") or "text/plain").strip()
    if content_type not in ("text/plain", "text/html"):
        content_type = "text/plain"
    conn_config = conn.get("config") or {}
    use_tls = conn_config.get("use_tls", True)
    smtp_host = get_decrypted_secret(ctx.client, cid, "SMTP_HOST", ctx.settings)
    smtp_port = get_decrypted_secret(ctx.client, cid, "SMTP_PORT", ctx.settings)
    smtp_user = get_decrypted_secret(ctx.client, cid, "SMTP_USERNAME", ctx.settings)
    smtp_pass = get_decrypted_secret(ctx.client, cid, "SMTP_PASSWORD", ctx.settings)
    smtp_from = get_decrypted_secret(ctx.client, cid, "SMTP_FROM", ctx.settings)
    if not smtp_host:
        raise ToolValidationError("Email connector missing SMTP_HOST secret")
    if not smtp_from:
        raise ToolValidationError("Email connector missing SMTP_FROM secret")
    port = int(smtp_port) if smtp_port else (587 if use_tls else 25)
    to_domain = extract_to_domain(to_addr)
    subj_h = _subject_hash(subject)
    body_h = _body_hash(body)
    msg_id, latency_ms = send_email_smtp(
        host=smtp_host,
        port=port,
        username=smtp_user or "",
        password=smtp_pass or "",
        from_addr=smtp_from,
        to_addr=to_addr,
        subject=subject,
        body=body,
        content_type=content_type,
        use_tls=use_tls,
    )
    out: dict[str, Any] = {
        "simulated": False,
        "to_domain": to_domain,
        "subject_hash": subj_h,
        "body_hash": body_h,
        "content_type": content_type,
    }
    if msg_id:
        out["message_id"] = msg_id[:200]
    return NormalizedResult(
        success=True,
        action="email.send",
        connector_id=cid,
        latency_ms=latency_ms,
        data=out,
    )


def _exec_webhook_post(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    if not connector_id:
        raise ToolValidationError("webhook.post requires connector_id")
    conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("Connector not found")
    if conn.get("type") != "webhook":
        raise ToolValidationError("Connector must be type webhook")
    if conn.get("status") != "active":
        raise ToolValidationError("Connector must be active")
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "webhook", cid)
    conn_cfg = parse_connector_config(conn.get("config") or {})
    allowed_hosts = conn_cfg["allowed_hosts"]
    target_host = allowed_hosts[0]
    path = params.get("path") or conn_cfg.get("default_path") or "/"
    path = validate_path(str(path))
    payload = params.get("payload")
    if payload is None:
        raise ToolValidationError("webhook.post requires payload")
    payload_bytes = coerce_payload(payload)
    if len(payload_bytes) > conn_cfg["max_payload_bytes"]:
        raise ToolValidationError("webhook.post payload exceeds max_payload_bytes")
    step_headers = params.get("headers") or {}
    sanitize_headers(step_headers)
    ips = resolve_and_validate_host(target_host)
    connect_ip = ips[0]
    bearer_token = get_decrypted_secret(ctx.client, cid, "WEBHOOK_BEARER_TOKEN", ctx.settings)
    hmac_secret = get_decrypted_secret(ctx.client, cid, "WEBHOOK_HMAC_SECRET", ctx.settings)
    secret_headers: dict[str, str] = {}
    rows = (
        ctx.client.table("connector_secrets")
        .select("key_name, encrypted_value")
        .eq("connector_id", cid)
        .execute()
    )
    for row in rows.data or []:
        key_name = row.get("key_name", "")
        if not key_name.startswith("WEBHOOK_HEADER_"):
            continue
        header_name = key_name[len("WEBHOOK_HEADER_") :].replace("_", "-")
        if header_name.lower() not in WEBHOOK_ALLOWED_HEADERS:
            raise ToolValidationError(f"Header {header_name!r} not allowlisted")
        secret_val = decrypt_secret(row["encrypted_value"], ctx.settings.connector_secrets_encryption_key)
        secret_headers[header_name] = secret_val
    headers, preview_keys, request_id = build_headers(
        step_headers=step_headers,
        secret_headers=secret_headers,
        bearer_token=bearer_token,
        hmac_secret=hmac_secret,
        payload_bytes=payload_bytes,
    )
    build_url(target_host, path, conn_cfg["allowed_schemes"])
    p_hash = _payload_hash(payload_bytes)
    status_code, response_time_ms = send_webhook(
        host=target_host,
        path=path,
        connect_ip=connect_ip,
        payload_bytes=payload_bytes,
        headers=headers,
        timeout_seconds=conn_cfg["timeout_seconds"],
        retry_count=conn_cfg["retry_count"],
        retry_backoff_ms=conn_cfg["retry_backoff_ms"],
    )
    return NormalizedResult(
        success=True,
        action="webhook.post",
        connector_id=cid,
        latency_ms=int(response_time_ms),
        data={
            "simulated": False,
            "target_host": target_host,
            "path": path,
            "payload_hash": p_hash,
            "payload_bytes": len(payload_bytes),
            "status_code": status_code,
            "response_time_ms": int(response_time_ms),
            "retry_count_used": conn_cfg["retry_count"],
            "request_id": request_id,
            "headers_preview": preview_keys,
        },
    )


_TOOL_REGISTRY: dict[str, ToolExecutor] = {
    "slack.post_message": _exec_slack_post_message,
    "email.send": _exec_email_send,
    "webhook.post": _exec_webhook_post,
    "hubspot.contacts.get": _exec_hubspot_contacts_get,
    "hubspot.contacts.update": _exec_hubspot_contacts_update,
    "hubspot.notes.create": _exec_hubspot_notes_create,
    "hubspot.deals.update_stage": _exec_hubspot_deals_update_stage,
    "hubspot.sequences.enroll": _exec_hubspot_sequences_enroll,
    "hubspot.contacts.create": _exec_hubspot_contacts_create,
    "hubspot.contacts.search": _exec_hubspot_contacts_search,
    "hubspot.deals.get": _exec_hubspot_deals_get,
    "hubspot.deals.create": _exec_hubspot_deals_create,
    "hubspot.deals.update": _exec_hubspot_deals_update,
    "hubspot.lists.add_contact": _exec_hubspot_lists_add_contact,
}

# Workflow step type → canonical tool action
STEP_TYPE_TO_ACTION: dict[str, str] = {
    "slack_post_message": "slack.post_message",
    "email_send": "email.send",
    "webhook_post": "webhook.post",
}


def list_registered_actions() -> list[str]:
    return sorted(_TOOL_REGISTRY.keys())


def invoke_tool(ctx: ToolContext, action: str, params: dict[str, Any] | None = None) -> NormalizedResult:
    """Invoke a registered connector tool with audit, rate limits, retries, and agent permissions."""
    params = params or {}
    executor = _TOOL_REGISTRY.get(action)
    if not executor:
        raise ToolNotFoundError(f"Unknown tool action: {action}")

    connector_id = params.get("connector_id") or ctx.connector_id
    connector_type = action.split(".", 1)[0] if "." in action else action
    cid = str(connector_id) if connector_id else None
    try:
        assert_agent_tool_permission(ctx, action, cid, connector_type)
    except ToolPermissionDeniedError as exc:
        _write_tool_audit(
            ctx,
            action,
            cid,
            "tool.invoke.failed",
            {"error_code": exc.code, "error": str(exc)[:200]},
        )
        return NormalizedResult(
            success=False,
            action=action,
            error_code=exc.code,
            error_message=str(exc),
            connector_id=cid,
        )
    _write_tool_audit(ctx, action, cid, "tool.invoke.requested")

    last_error: ToolError | None = None
    attempts = _MAX_RETRIES + 1
    for attempt in range(attempts):
        started = time.perf_counter()
        try:
            result = executor(ctx, params)
            result.latency_ms = result.latency_ms or int((time.perf_counter() - started) * 1000)
            _write_tool_audit(
                ctx,
                action,
                result.connector_id,
                "tool.invoke.completed",
                {"latency_ms": result.latency_ms, "attempt": attempt + 1},
            )
            return result
        except Exception as exc:
            tool_exc = _classify_error(exc)
            last_error = tool_exc
            retryable = isinstance(tool_exc, ToolRateLimitedError) or (
                not isinstance(tool_exc, (ToolValidationError, ToolAuthExpiredError, ToolNotFoundError))
                and attempt < attempts - 1
            )
            if not retryable:
                break
            if attempt < len(_RETRY_BACKOFF_SEC):
                time.sleep(_RETRY_BACKOFF_SEC[attempt])

    assert last_error is not None
    _write_tool_audit(
        ctx,
        action,
        str(connector_id) if connector_id else None,
        "tool.invoke.failed",
        {"error_code": last_error.code, "error": str(last_error)[:200]},
    )
    return NormalizedResult(
        success=False,
        action=action,
        error_code=last_error.code,
        error_message=str(last_error),
        connector_id=str(connector_id) if connector_id else None,
    )


def tool_context_from_step(context: Any) -> ToolContext:
    """Build ToolContext from workflows StepContext."""
    return ToolContext(
        settings=context.settings,
        client=context.client,
        org_id=context.org_id,
        actor_id=context.user_id or "",
        environment_name=context.environment_name or "default",
        run_id=context.run_id,
        step_id=context.step_id,
        step_type=context.step_type,
        connector_id=(context.config or {}).get("connector_id"),
    )


def params_for_step(step_type: str, config: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    """Map workflow step config + parameters to invoke_tool params."""
    cfg = config or {}
    params = dict(parameters)
    if cfg.get("connector_id"):
        params["connector_id"] = cfg["connector_id"]
    if step_type == "slack_post_message":
        msg_key = cfg.get("message_input_key", "message")
        params["message"] = parameters.get(msg_key, parameters.get("message", ""))
        params["channel"] = cfg.get("channel") or parameters.get("channel", "")
    elif step_type == "email_send":
        params["to"] = parameters.get(cfg.get("to_input_key", "to"), "")
        params["subject"] = parameters.get(cfg.get("subject_input_key", "subject"), "")
        params["body"] = parameters.get(cfg.get("body_input_key", "body"), "")
        params["content_type"] = cfg.get("content_type", "text/plain")
    elif step_type == "webhook_post":
        payload_key = cfg.get("payload_input_key", "payload")
        params["payload"] = parameters.get(payload_key)
        params["path"] = cfg.get("path")
        params["headers"] = cfg.get("headers") or {}
    return params
