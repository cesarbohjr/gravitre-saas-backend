"""Step handler implementations for registry."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from app.config import Settings
from app.connectors.email import body_hash as _body_hash
from app.connectors.email import extract_to_domain
from app.connectors.email import subject_hash as _subject_hash
from app.connectors.repository import get_connector
from app.connectors.webhook import (
    coerce_payload,
    parse_connector_config,
    payload_hash as _payload_hash,
    sanitize_headers,
    validate_path,
)
from app.services.tool_service import (
    STEP_TYPE_TO_ACTION,
    invoke_tool,
    params_for_step,
    tool_context_from_step,
)
from app.rag.embedding import get_embedding
from app.rag.retrieval import search_chunks
from app.workflows.constants import OUTPUT_SNAPSHOT_MAX_BYTES
from app.services.handoff_service import execute_agent_step_with_handoff
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
        action = STEP_TYPE_TO_ACTION[self.step_type]
        result = invoke_tool(
            tool_context_from_step(context),
            action,
            params_for_step(self.step_type, context.config or {}, context.parameters),
        )
        return _truncate_output_snapshot(result.to_step_output())


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
        action = STEP_TYPE_TO_ACTION[self.step_type]
        result = invoke_tool(
            tool_context_from_step(context),
            action,
            params_for_step(self.step_type, context.config or {}, context.parameters),
        )
        return _truncate_output_snapshot(result.to_step_output())


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
        action = STEP_TYPE_TO_ACTION[self.step_type]
        result = invoke_tool(
            tool_context_from_step(context),
            action,
            params_for_step(self.step_type, context.config or {}, context.parameters),
        )
        return _truncate_output_snapshot(result.to_step_output())


def _step_def_from_config(config: dict[str, Any]) -> dict[str, Any]:
    metadata = config.get("metadata")
    if isinstance(metadata, dict):
        return {
            "metadata": metadata,
            "config": {k: v for k, v in config.items() if k != "metadata"},
        }
    return {"metadata": config, "config": config}


class AgentStepHandler(StepHandler):
    """STA-17/18: agent step with optional next_agent_id handoff routing."""

    step_type = "agent"

    def simulate(self, context: StepContext) -> dict[str, Any]:
        from app.services.handoff_service import resolve_step_agent_metadata

        step_def = _step_def_from_config(context.config or {})
        agent_id, next_agent_id, task = resolve_step_agent_metadata(step_def)
        return _truncate_output_snapshot(
            {
                "simulated": True,
                "agent_id": agent_id,
                "next_agent_id": next_agent_id,
                "task": task,
                "message": "Agent step simulated (dry-run)",
            }
        )

    def execute(self, context: StepContext) -> dict[str, Any]:
        if not context.client:
            raise ValueError("agent step requires database client")
        actor_id = context.user_id or context.org_id
        step_def = _step_def_from_config(context.config or {})
        output = asyncio.run(
            execute_agent_step_with_handoff(
                context.settings,
                org_id=context.org_id,
                user_id=str(actor_id),
                run_id=str(context.run_id or context.org_id),
                step_id=context.step_id,
                step_def=step_def,
                parameters=context.parameters,
                step_outputs=context.step_outputs,
                client=context.client,
            )
        )
        return _truncate_output_snapshot(output)


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
    register_handler(AgentStepHandler())
    register_handler(NoopHandler())
    register_handler(SlackPostMessageHandler())
    register_handler(EmailSendHandler())
    register_handler(WebhookPostHandler())
    register_handler(ConditionHandler())
    register_handler(TransformHandler())


register_handlers()
