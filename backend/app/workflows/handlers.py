"""Step handler implementations for registry."""
from __future__ import annotations

import json
from typing import Any

from app.config import Settings
from app.connectors.crypto import decrypt_secret
from app.connectors.email import body_hash as _body_hash
from app.connectors.email import extract_to_domain
from app.connectors.email import send_email_smtp
from app.connectors.email import subject_hash as _subject_hash
from app.connectors.rate_limit import enforce_rate_limit
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
from app.rag.embedding import get_embedding
from app.rag.retrieval import search_chunks
from app.workflows.audit import write_audit_event
from app.workflows.constants import OUTPUT_SNAPSHOT_MAX_BYTES, RESOURCE_TYPE_WORKFLOW_RUN
from app.workflows.registry import StepContext, StepHandler, register_handler


def _truncate_output_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(data, separators=(",", ":"))
    if len(raw.encode("utf-8")) <= OUTPUT_SNAPSHOT_MAX_BYTES:
        return data
    return {"truncated": True, "size_exceeded": True, "original_bytes": len(raw.encode("utf-8"))}


def _rag_retrieve(
    settings: Settings,
    org_id: str,
    parameters: dict[str, Any],
    config: dict[str, Any],
    environment_name: str = "default",
) -> dict[str, Any]:
    """Call BE-10 retrieval (read-only). Returns output for output_snapshot; raises on failure."""
    query_key = config.get("query_input_key", "query")
    query = parameters.get(query_key)
    if not isinstance(query, str) or not query.strip():
        raise ValueError("rag_retrieve requires non-empty query in parameters")
    top_k = min(int(config.get("top_k", 10)), 50)
    if top_k < 1:
        top_k = 10
    embedding = get_embedding(query.strip(), settings)
    rows = search_chunks(
        settings=settings,
        org_id=org_id,
        query_embedding=embedding,
        top_k=top_k,
        source_id=None,
        document_id=None,
        environment_name=environment_name,
    )
    chunks = [
        {
            "id": str(r["chunk_id"]),
            "text": r["content"],
            "source_id": str(r["source_id"]),
            "source_title": r.get("source_title") or "",
            "document_id": str(r["document_id"]),
            "document_title": r.get("document_title"),
            "chunk_index": r["chunk_index"],
            "score": round(float(r["score"]), 6),
        }
        for r in rows
    ]
    import uuid
    output = {"query_id": str(uuid.uuid4()), "chunks": chunks, "total": len(chunks)}
    return _truncate_output_snapshot(output)


class RagRetrieveHandler(StepHandler):
    step_type = "rag_retrieve"

    def simulate(self, context: StepContext) -> dict[str, Any]:
        return _rag_retrieve(
            context.settings,
            context.org_id,
            context.parameters,
            context.config,
            environment_name=context.environment_name or "default",
        )

    def execute(self, context: StepContext) -> dict[str, Any]:
        return _rag_retrieve(
            context.settings,
            context.org_id,
            context.parameters,
            context.config,
            environment_name=context.environment_name or "default",
        )


class NoopHandler(StepHandler):
    step_type = "noop"

    def simulate(self, context: StepContext) -> dict[str, Any]:
        return _truncate_output_snapshot({"simulated": True, "message": "No-op (dry-run)"})

    def execute(self, context: StepContext) -> dict[str, Any]:
        return _truncate_output_snapshot({"executed": True, "message": "No-op"})


class SlackPostMessageHandler(StepHandler):
    step_type = "slack_post_message"

    def simulate(self, context: StepContext) -> dict[str, Any]:
        cfg = context.config or {}
        channel = cfg.get("channel") or context.parameters.get("channel", "") or "<channel>"
        msg_key = cfg.get("message_input_key", "message")
        msg = context.parameters.get(msg_key, "") or ""
        return _truncate_output_snapshot({
            "simulated": True,
            "message": "Slack post simulated (dry-run)",
            "predicted_channel": str(channel)[:80],
            "predicted_message_preview": str(msg)[:100] if msg else "(empty)",
        })

    def execute(self, context: StepContext) -> dict[str, Any]:
        settings = context.settings
        org_id = context.org_id
        parameters = context.parameters
        config = context.config
        client = context.client
        run_id = context.run_id or ""
        user_id = context.user_id or ""
        step_id = context.step_id
        environment = context.environment_name or "default"

        cfg = config or {}
        if settings.disable_connectors:
            raise ValueError("Connectors are disabled")
        connector_id = cfg.get("connector_id")
        if connector_id:
            conn = get_connector(client, org_id, str(connector_id), environment_name=environment)
        else:
            conn = get_connector_by_type(client, org_id, "slack", environment_name=environment)
        if not conn:
            raise ValueError("No active Slack connector found for org")
        enforce_rate_limit(client, org_id, "slack_post_message", "slack", str(conn["id"]))
        token = get_decrypted_secret(client, str(conn["id"]), "token", settings)
        if not token:
            raise ValueError("Slack connector missing token secret")
        channel = (cfg.get("channel") or parameters.get("channel") or "").strip()
        if not channel:
            raise ValueError("Slack channel is required (config.channel or parameters.channel)")
        msg_key = cfg.get("message_input_key", "message")
        text = (parameters.get(msg_key) or "").strip()
        if not text:
            raise ValueError(f"Slack message is required (parameters.{msg_key})")
        write_audit_event(
            client, org_id, user_id,
            action="slack.send.requested",
            resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
            resource_id=run_id,
            metadata={"step_id": step_id, "channel": channel[:80], "message_hash": message_hash(text)},
        )
        try:
            result = send_slack_message(token, channel, text)
        except ValueError as e:
            write_audit_event(
                client, org_id, user_id,
                action="slack.send.failed",
                resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
                resource_id=run_id,
                metadata={"step_id": step_id, "error": str(e)[:200]},
            )
            raise
        write_audit_event(
            client, org_id, user_id,
            action="slack.send.sent",
            resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
            resource_id=run_id,
            metadata={
                "step_id": step_id,
                "channel": channel[:80],
                "ts": result.get("ts", "")[:30],
                "latency_ms": int(result.get("_latency_ms", 0) or 0),
            },
        )
        return _truncate_output_snapshot({"executed": True, "channel": channel, "ts": result.get("ts"), "ok": True})


class EmailSendHandler(StepHandler):
    step_type = "email_send"

    def simulate(self, context: StepContext) -> dict[str, Any]:
        cfg = context.config or {}
        params = context.parameters or {}
        environment = context.environment_name or "default"
        to_key = cfg.get("to_input_key", "to")
        subj_key = cfg.get("subject_input_key", "subject")
        body_key = cfg.get("body_input_key", "body")
        to_addr = str(params.get(to_key, ""))
        subject = str(params.get(subj_key, ""))
        body = str(params.get(body_key, ""))
        if not to_addr.strip():
            raise ValueError(f"email_send requires parameters.{to_key}")
        if not subject:
            raise ValueError(f"email_send requires parameters.{subj_key}")
        if not body:
            raise ValueError(f"email_send requires parameters.{body_key}")
        connector_id = cfg.get("connector_id")
        if not connector_id:
            raise ValueError("email_send requires config.connector_id")
        if context.client and context.org_id:
            conn = get_connector(context.client, context.org_id, str(connector_id), environment_name=environment)
            if not conn:
                raise ValueError(f"Connector {connector_id} not found")
            if conn.get("type") != "email":
                raise ValueError("Connector must be type email")
            if conn.get("status") != "active":
                raise ValueError("Connector must be active")
        content_type = cfg.get("content_type", "text/plain") or "text/plain"
        if content_type not in ("text/plain", "text/html"):
            content_type = "text/plain"
        return _truncate_output_snapshot({
            "simulated": True,
            "to_domain": extract_to_domain(to_addr),
            "subject_hash": _subject_hash(subject),
            "body_hash": _body_hash(body),
            "content_type": content_type,
        })

    def execute(self, context: StepContext) -> dict[str, Any]:
        settings = context.settings
        org_id = context.org_id
        parameters = context.parameters
        config = context.config
        client = context.client
        run_id = context.run_id or ""
        user_id = context.user_id or ""
        step_id = context.step_id
        environment = context.environment_name or "default"

        cfg = config or {}
        if settings.disable_connectors:
            raise ValueError("Connectors are disabled")
        connector_id = cfg.get("connector_id")
        if not connector_id:
            raise ValueError("email_send requires config.connector_id")
        conn = get_connector(client, org_id, str(connector_id), environment_name=environment)
        if not conn:
            raise ValueError("Connector not found")
        if conn.get("type") != "email":
            raise ValueError("Connector must be type email")
        enforce_rate_limit(client, org_id, "email_send", "email", str(conn["id"]))
        to_key = cfg.get("to_input_key", "to")
        subj_key = cfg.get("subject_input_key", "subject")
        body_key = cfg.get("body_input_key", "body")
        to_addr = (parameters.get(to_key) or "").strip()
        subject = str(parameters.get(subj_key, ""))
        body = str(parameters.get(body_key, ""))
        if not to_addr:
            raise ValueError(f"email_send requires parameters.{to_key}")
        content_type = (cfg.get("content_type") or "text/plain").strip()
        if content_type not in ("text/plain", "text/html"):
            content_type = "text/plain"
        conn_config = conn.get("config") or {}
        use_tls = conn_config.get("use_tls", True)
        smtp_host = get_decrypted_secret(client, str(conn["id"]), "SMTP_HOST", settings)
        smtp_port = get_decrypted_secret(client, str(conn["id"]), "SMTP_PORT", settings)
        smtp_user = get_decrypted_secret(client, str(conn["id"]), "SMTP_USERNAME", settings)
        smtp_pass = get_decrypted_secret(client, str(conn["id"]), "SMTP_PASSWORD", settings)
        smtp_from = get_decrypted_secret(client, str(conn["id"]), "SMTP_FROM", settings)
        if not smtp_host:
            raise ValueError("Email connector missing SMTP_HOST secret")
        if not smtp_from:
            raise ValueError("Email connector missing SMTP_FROM secret")
        port = int(smtp_port) if smtp_port else (587 if use_tls else 25)
        to_domain = extract_to_domain(to_addr)
        subj_h = _subject_hash(subject)
        body_h = _body_hash(body)
        write_audit_event(
            client, org_id, user_id,
            action="email.send.requested",
            resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
            resource_id=run_id,
            metadata={"step_id": step_id, "to_domain": to_domain, "subject_hash": subj_h, "body_hash": body_h},
        )
        try:
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
        except ValueError as e:
            write_audit_event(
                client, org_id, user_id,
                action="email.send.failed",
                resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
                resource_id=run_id,
                metadata={"step_id": step_id, "to_domain": to_domain, "error": str(e)[:200]},
            )
            raise
        write_audit_event(
            client, org_id, user_id,
            action="email.send.sent",
            resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
            resource_id=run_id,
            metadata={
                "step_id": step_id,
                "to_domain": to_domain,
                "subject_hash": subj_h,
                "body_hash": body_h,
                "latency_ms": latency_ms,
            },
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
        return _truncate_output_snapshot(out)


class WebhookPostHandler(StepHandler):
    step_type = "webhook_post"

    def simulate(self, context: StepContext) -> dict[str, Any]:
        cfg = context.config or {}
        params = context.parameters or {}
        environment = context.environment_name or "default"
        connector_id = cfg.get("connector_id")
        if not connector_id:
            raise ValueError("webhook_post requires config.connector_id")
        if not context.client or not context.org_id:
            raise ValueError("webhook_post requires org context")
        conn = get_connector(context.client, context.org_id, str(connector_id), environment_name=environment)
        if not conn:
            raise ValueError("Connector not found")
        if conn.get("type") != "webhook":
            raise ValueError("Connector must be type webhook")
        if conn.get("status") != "active":
            raise ValueError("Connector must be active")
        conn_cfg = parse_connector_config(conn.get("config") or {})
        allowed_hosts = conn_cfg["allowed_hosts"]
        target_host = allowed_hosts[0]
        path = cfg.get("path") or conn_cfg.get("default_path") or "/"
        path = validate_path(path)
        payload_key = cfg.get("payload_input_key", "payload")
        if payload_key not in params:
            raise ValueError(f"webhook_post requires parameters.{payload_key}")
        payload_bytes = coerce_payload(params[payload_key])
        if len(payload_bytes) > conn_cfg["max_payload_bytes"]:
            raise ValueError("webhook_post payload exceeds max_payload_bytes")
        headers = cfg.get("headers") or {}
        sanitized = sanitize_headers(headers)
        return _truncate_output_snapshot({
            "simulated": True,
            "target_host": target_host,
            "path": path,
            "payload_hash": _payload_hash(payload_bytes),
            "payload_bytes": len(payload_bytes),
            "headers_preview": list(sanitized.keys()),
        })

    def execute(self, context: StepContext) -> dict[str, Any]:
        settings = context.settings
        org_id = context.org_id
        parameters = context.parameters
        config = context.config
        client = context.client
        run_id = context.run_id or ""
        user_id = context.user_id or ""
        step_id = context.step_id
        environment = context.environment_name or "default"

        cfg = config or {}
        if settings.disable_connectors:
            raise ValueError("Connectors are disabled")
        connector_id = cfg.get("connector_id")
        if not connector_id:
            raise ValueError("webhook_post requires config.connector_id")
        conn = get_connector(client, org_id, str(connector_id), environment_name=environment)
        if not conn:
            raise ValueError("Connector not found")
        if conn.get("type") != "webhook":
            raise ValueError("Connector must be type webhook")
        if conn.get("status") != "active":
            raise ValueError("Connector must be active")
        enforce_rate_limit(client, org_id, "webhook_post", "webhook", str(conn["id"]))
        conn_cfg = parse_connector_config(conn.get("config") or {})
        allowed_hosts = conn_cfg["allowed_hosts"]
        target_host = allowed_hosts[0]
        path = cfg.get("path") or conn_cfg.get("default_path") or "/"
        path = validate_path(path)
        payload_key = cfg.get("payload_input_key", "payload")
        if payload_key not in parameters:
            raise ValueError(f"webhook_post requires parameters.{payload_key}")
        payload_bytes = coerce_payload(parameters[payload_key])
        if len(payload_bytes) > conn_cfg["max_payload_bytes"]:
            raise ValueError("webhook_post payload exceeds max_payload_bytes")
        step_headers = cfg.get("headers") or {}
        sanitize_headers(step_headers)

        ips = resolve_and_validate_host(target_host)
        connect_ip = ips[0]

        bearer_token = get_decrypted_secret(client, str(conn["id"]), "WEBHOOK_BEARER_TOKEN", settings)
        hmac_secret = get_decrypted_secret(client, str(conn["id"]), "WEBHOOK_HMAC_SECRET", settings)
        secret_headers: dict[str, str] = {}
        rows = (
            client.table("connector_secrets")
            .select("key_name, encrypted_value")
            .eq("connector_id", str(conn["id"]))
            .execute()
        )
        for row in (rows.data or []):
            key_name = row.get("key_name", "")
            if not key_name.startswith("WEBHOOK_HEADER_"):
                continue
            header_name = key_name[len("WEBHOOK_HEADER_") :].replace("_", "-")
            if header_name.lower() not in WEBHOOK_ALLOWED_HEADERS:
                raise ValueError(f"Header {header_name!r} not allowlisted")
            secret_val = decrypt_secret(row["encrypted_value"], settings.connector_secrets_encryption_key)
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
        write_audit_event(
            client, org_id, user_id,
            action="webhook.send.requested",
            resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
            resource_id=run_id,
            metadata={
                "step_id": step_id,
                "target_host": target_host,
                "payload_hash": p_hash,
                "payload_bytes": len(payload_bytes),
                "request_id": request_id,
            },
        )
        try:
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
        except ValueError as e:
            write_audit_event(
                client, org_id, user_id,
                action="webhook.send.failed",
                resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
                resource_id=run_id,
                metadata={
                    "step_id": step_id,
                    "target_host": target_host,
                    "payload_hash": p_hash,
                    "payload_bytes": len(payload_bytes),
                    "request_id": request_id,
                    "error_code": "webhook_failed",
                },
            )
            raise
        write_audit_event(
            client, org_id, user_id,
            action="webhook.send.sent",
            resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
            resource_id=run_id,
            metadata={
                "step_id": step_id,
                "target_host": target_host,
                "status_code": status_code,
                "response_time_ms": int(response_time_ms),
                "latency_ms": int(response_time_ms),
                "payload_hash": p_hash,
                "payload_bytes": len(payload_bytes),
                "request_id": request_id,
            },
        )
        return _truncate_output_snapshot({
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
        })


class ConditionHandler(StepHandler):
    step_type = "condition"
    supports_execute = False

    def simulate(self, context: StepContext) -> dict[str, Any]:
        return _truncate_output_snapshot({"simulated": True, "branch": "default"})

    def execute(self, context: StepContext) -> dict[str, Any]:
        raise ValueError(f"Invalid step type for execute: {context.step_type}")


class TransformHandler(StepHandler):
    step_type = "transform"
    supports_execute = False

    def simulate(self, context: StepContext) -> dict[str, Any]:
        template = (context.config or {}).get("template") or ""
        out: dict[str, Any] = {"simulated": True, "message": "Transform applied (dry-run)"}
        if template and "{{steps." in template and ".output}}" in template:
            for sid, prev in context.step_outputs.items():
                template = template.replace(f"{{{{steps.{sid}.output}}}}", json.dumps(prev)[:200])
            out["evaluated_template_preview"] = template[:500]
        return _truncate_output_snapshot(out)

    def execute(self, context: StepContext) -> dict[str, Any]:
        raise ValueError(f"Invalid step type for execute: {context.step_type}")


def register_handlers() -> None:
    register_handler(RagRetrieveHandler())
    register_handler(NoopHandler())
    register_handler(SlackPostMessageHandler())
    register_handler(EmailSendHandler())
    register_handler(WebhookPostHandler())
    register_handler(ConditionHandler())
    register_handler(TransformHandler())


register_handlers()
