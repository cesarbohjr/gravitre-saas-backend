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
from app.services.handoff_service import execute_agent_step_with_handoff
from app.services.unified_retrieval_service import (
    be10_rows_to_workflow_chunks,
    get_unified_retrieval_service,
)
from app.workflows.constants import OUTPUT_SNAPSHOT_MAX_BYTES
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
    client: Any | None = None,
) -> dict[str, Any]:
    """Call unified retrieval (read-only). Returns output for output_snapshot; raises on failure."""
    query_key = config.get("query_input_key", "query")
    query = parameters.get(query_key)
    if not isinstance(query, str) or not query.strip():
        raise ValueError("rag_retrieve requires non-empty query in parameters")
    top_k = min(int(config.get("top_k", 10)), 50)
    if top_k < 1:
        top_k = 10
    agent_id = str(config.get("agent_id")) if config.get("agent_id") else None
    department_id = str(config.get("department_id")) if config.get("department_id") else None
    source_id = str(config.get("source_id")) if config.get("source_id") else None

    async def _run() -> list[dict[str, Any]]:
        rows, _metrics = await get_unified_retrieval_service().retrieve_knowledge_rows(
            org_id=org_id,
            query=query.strip(),
            top_k=top_k,
            environment_name=environment_name,
            agent_id=agent_id,
            department_id=department_id,
            source_id=source_id,
            scope="agent" if agent_id else "organization",
        )
        return rows

    try:
        rows = asyncio.run(_run())
    except Exception as exc:
        raise ValueError(f"rag_retrieve failed: {exc}") from exc

    chunks = be10_rows_to_workflow_chunks(rows)
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
            client=context.client,
        )

    def execute(self, context: StepContext) -> dict[str, Any]:
        return _rag_retrieve(
            context.settings,
            context.org_id,
            context.parameters,
            context.config,
            environment_name=context.environment_name or "default",
            client=context.client,
        )


class NoopHandler(StepHandler):
    step_type = "noop"

    def simulate(self, context: StepContext) -> dict[str, Any]:
        return _truncate_output_snapshot({"simulated": True, "message": "No-op (dry-run)"})

    def execute(self, context: StepContext) -> dict[str, Any]:
        return _truncate_output_snapshot({"executed": True, "message": "No-op"})


def _enforce_canvas_write_authority(context: StepContext) -> None:
    """Block catalog write steps unless the run required human approval (P1 canvas gate)."""
    from app.services.canvas_write_gate import (
        CANVAS_WRITE_AUTHORITY_BLOCKED,
        block_canvas_write_step,
        load_run_for_write_gate,
    )

    run_row = load_run_for_write_gate(context.client, context.org_id, context.run_id)
    blocked = block_canvas_write_step(
        step_type=context.step_type,
        config=context.config,
        run_row=run_row,
    )
    if blocked:
        raise PermissionError(
            f"{CANVAS_WRITE_AUTHORITY_BLOCKED}: {blocked.get('error')}"
        )


class InvokeToolHandler(StepHandler):
    """STA-39: run a registered connector tool action from workflow config."""

    step_type = "invoke_tool"

    def simulate(self, context: StepContext) -> dict[str, Any]:
        cfg = context.config or {}
        action = cfg.get("action") or ""
        return _truncate_output_snapshot(
            {
                "simulated": True,
                "action": action,
                "message": "Tool invoke simulated (dry-run)",
            }
        )

    def execute(self, context: StepContext) -> dict[str, Any]:
        cfg = context.config or {}
        action = cfg.get("action")
        if not action:
            raise ValueError("invoke_tool requires config.action")
        _enforce_canvas_write_authority(context)
        result = invoke_tool(
            tool_context_from_step(context),
            str(action),
            params_for_step(
                "invoke_tool",
                cfg,
                context.parameters,
                step_outputs=context.step_outputs,
            ),
        )
        return _truncate_output_snapshot(result.to_step_output())


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
        _enforce_canvas_write_authority(context)
        action = STEP_TYPE_TO_ACTION[self.step_type]
        result = invoke_tool(
            tool_context_from_step(context),
            action,
            params_for_step(
                self.step_type,
                context.config or {},
                context.parameters,
                step_outputs=context.step_outputs,
            ),
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
        _enforce_canvas_write_authority(context)
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
        _enforce_canvas_write_authority(context)
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


class CouncilStepHandler(StepHandler):
    """STA-48: convene agent council and select a workflow branch."""

    step_type = "council"

    def simulate(self, context: StepContext) -> dict[str, Any]:
        cfg = context.config or {}
        options = cfg.get("options") or ["enroll", "nurture"]
        return _truncate_output_snapshot(
            {
                "simulated": True,
                "branch": str(options[0]),
                "escalated": True,
                "message": "Council step simulated (dry-run)",
            }
        )

    def execute(self, context: StepContext) -> dict[str, Any]:
        from app.services.council_workflow_service import execute_council_step

        if not context.client:
            raise ValueError("council step requires database client")
        workflow_id = str((context.parameters or {}).get("workflow_id") or context.run_id or "")
        output = asyncio.run(
            execute_council_step(
                context.settings,
                org_id=context.org_id,
                user_id=str(context.user_id or context.org_id),
                run_id=str(context.run_id or context.org_id),
                workflow_id=workflow_id,
                step_id=context.step_id,
                config=context.config or {},
                parameters=context.parameters,
                step_outputs=context.step_outputs,
                client=context.client,
            )
        )
        return _truncate_output_snapshot(output)


def _eval_simple_condition(expression: Any, parameters: dict[str, Any] | None) -> tuple[bool, str]:
    """Safe, intentionally limited condition eval for IF/Switch dry-run + execute.

    Supports:
    - empty → True (default branch)
    - literal true/false / 1/0
    - param key presence: ``$foo`` / ``params.foo`` truthiness
    - equality: ``$status == closed`` / ``params.stage == won``
    """
    text = str(expression or "").strip()
    if not text:
        return True, "default"
    params = parameters or {}
    lower = text.lower()
    if lower in {"true", "1", "yes"}:
        return True, "true"
    if lower in {"false", "0", "no"}:
        return False, "false"

    # equality: left == right
    if "==" in text:
        left, right = [p.strip() for p in text.split("==", 1)]
        left_val = _resolve_condition_operand(left, params)
        right_val = _resolve_condition_operand(right, params)
        ok = str(left_val).strip().lower() == str(right_val).strip().lower()
        return ok, "true" if ok else "false"

    # bare param / $param truthiness
    val = _resolve_condition_operand(text, params)
    ok = bool(val) and str(val).strip().lower() not in {"false", "0", "none", "null", ""}
    return ok, "true" if ok else "false"


def _resolve_condition_operand(token: str, params: dict[str, Any]) -> Any:
    raw = token.strip().strip("'\"")
    if raw.startswith("$"):
        return params.get(raw[1:])
    if raw.startswith("params."):
        return params.get(raw[len("params.") :])
    if raw in params:
        return params.get(raw)
    return raw


class ConditionHandler(StepHandler):
    step_type = "condition"
    supports_execute = True

    def simulate(self, context: StepContext) -> dict[str, Any]:
        cfg = context.config or {}
        ok, branch = _eval_simple_condition(cfg.get("expression") or cfg.get("condition"), context.parameters)
        default = str(cfg.get("default_branch") or "default")
        chosen = branch if ok or branch in {"true", "false"} else default
        if not ok and branch == "false":
            chosen = "false"
        return _truncate_output_snapshot(
            {
                "simulated": True,
                "branch": chosen,
                "matched": ok,
                "expression": cfg.get("expression") or cfg.get("condition"),
                "builder_node_type": cfg.get("builder_node_type"),
            }
        )

    def execute(self, context: StepContext) -> dict[str, Any]:
        cfg = context.config or {}
        ok, branch = _eval_simple_condition(cfg.get("expression") or cfg.get("condition"), context.parameters)
        return _truncate_output_snapshot(
            {
                "branch": branch,
                "matched": ok,
                "expression": cfg.get("expression") or cfg.get("condition"),
                "builder_node_type": cfg.get("builder_node_type"),
                "when_branch": branch,
            }
        )


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


class ApprovalStepHandler(StepHandler):
    """Linear-path Quality Gate — pauses the run (graph path uses execution_engine)."""

    step_type = "approval"

    def simulate(self, context: StepContext) -> dict[str, Any]:
        return _truncate_output_snapshot(
            {"simulated": True, "message": "Approval gate (dry-run)", "pending_approval": True}
        )

    def execute(self, context: StepContext) -> dict[str, Any]:
        # Linear execute cannot mid-pause the same way as the graph engine; fail closed
        # so a human_approval that only exists as a step cannot be skipped as a noop.
        raise PermissionError(
            "approval step requires graph execution pause (awaiting_approval); "
            "refusing to skip Quality Gate on linear path"
        )


def register_handlers() -> None:
    register_handler(RagRetrieveHandler())
    register_handler(AgentStepHandler())
    register_handler(NoopHandler())
    register_handler(InvokeToolHandler())
    register_handler(CouncilStepHandler())
    register_handler(SlackPostMessageHandler())
    register_handler(EmailSendHandler())
    register_handler(WebhookPostHandler())
    register_handler(ConditionHandler())
    register_handler(TransformHandler())
    register_handler(ApprovalStepHandler())


register_handlers()
