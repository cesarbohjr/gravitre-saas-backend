"""Live execution helpers for multi-step chat workflow E2E scenarios."""
from __future__ import annotations

import re
from contextlib import asynccontextmanager, contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from unittest.mock import patch

from app.services.chat_connector_execution_service import (
    ChatConnectorExecutionService,
    ConnectorActionPlan,
)
from app.services.chat_connector_models import INTEGRATION_ALIASES
from app.services.chat_orchestration_service import ChatOrchestrationService
from app.services.conversation_state_service import DEFAULT_TASK_STATE
from app.services.conversational_execution_service import ExecutionResult
from app.services.oauth_smoke_runner import _is_sandbox_write_allowed

StepLiveStatus = Literal["passed", "failed", "skipped", "blocked"]

_DELETE_ACTION = re.compile(r"\.(delete|remove|archive)\b", re.I)
_GOOGLE_FAMILY = frozenset({"google_drive", "google_sheets", "google_docs"})
_WORKFLOW_PREFIX = "Gravitre Workflow E2E"


@dataclass(frozen=True)
class LiveWorkflowOptions:
    enable_writes: bool = False
    allow_destructive: bool = False
    auto_cleanup: bool = False
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class WorkflowCleanupRecord:
    integration: str
    invoke_action: str
    resource_type: str
    resource_id: str
    manual_instruction: str
    auto_cleanup_action: str | None = None
    auto_cleanup_status: str | None = None
    auto_cleanup_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "integration": self.integration,
            "invokeAction": self.invoke_action,
            "resourceType": self.resource_type,
            "resourceId": self.resource_id,
            "manualInstruction": self.manual_instruction,
            "autoCleanupAction": self.auto_cleanup_action,
            "autoCleanupStatus": self.auto_cleanup_status,
            "autoCleanupDetail": self.auto_cleanup_detail,
        }


@dataclass
class WorkflowStepRecord:
    step_id: str
    invoke_action: str
    kind: str
    status: StepLiveStatus
    request_payload: dict[str, Any] = field(default_factory=dict)
    response_shape: dict[str, Any] = field(default_factory=dict)
    audit_event_ids: list[str] = field(default_factory=list)
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stepId": self.step_id,
            "invokeAction": self.invoke_action,
            "kind": self.kind,
            "status": self.status,
            "requestPayload": self.request_payload,
            "responseShape": self.response_shape,
            "auditEventIds": self.audit_event_ids,
            "failureReason": self.failure_reason,
        }


def workflow_run_tag(run_id: str) -> str:
    return run_id.replace("-", "")[:14]


def resolve_live_connected_integrations(
    connector: ChatConnectorExecutionService,
    *,
    client: Any,
    org_id: str,
    scenario_integrations: tuple[str, ...],
    environment_name: str,
) -> tuple[list[str], list[str]]:
    """Return (connected, missing) using stored OAuth connectors for the org."""
    live = {
        c.lower()
        for c in connector._live_connected_integrations(  # noqa: SLF001
            client,
            org_id,
            environment_name=environment_name,
        )
    }
    expanded = set(live)
    if live & _GOOGLE_FAMILY:
        expanded |= _GOOGLE_FAMILY
    required = [i.lower() for i in scenario_integrations]
    connected = [i for i in required if i in expanded]
    missing = [i for i in required if i not in expanded]
    return connected, missing


def create_workflow_conversation(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    scenario_id: str,
    run_id: str,
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "org_id": org_id,
        "user_id": user_id,
        "title": f"{_WORKFLOW_PREFIX} {scenario_id} {run_id[:8]}",
        "preview": None,
        "message_count": 0,
        "created_at": now,
        "updated_at": now,
        "task_state": deepcopy(DEFAULT_TASK_STATE),
    }
    response = client.table("conversations").insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError("Failed to create workflow E2E conversation")
    return str(data[0]["id"])


def summarize_response_shape(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        keys = sorted(str(k) for k in payload.keys())
        return {"type": "object", "keys": keys[:25], "keyCount": len(keys)}
    if isinstance(payload, list):
        sample = payload[0] if payload else None
        return {
            "type": "array",
            "length": len(payload),
            "itemShape": summarize_response_shape(sample) if sample is not None else None,
        }
    return {"type": type(payload).__name__}


def _missing_write_env(plan: ConnectorActionPlan, env: dict[str, str]) -> str | None:
    if plan.invoke_action == "slack.post_message":
        channel = env.get("CHAT_WORKFLOW_E2E_SLACK_CHANNEL") or env.get("OAUTH_SMOKE_SLACK_CHANNEL")
        if not channel:
            return "CHAT_WORKFLOW_E2E_SLACK_CHANNEL or OAUTH_SMOKE_SLACK_CHANNEL"
    if plan.invoke_action in {"hubspot.deals.update", "hubspot.deals.update_stage"}:
        if not env.get("CHAT_WORKFLOW_E2E_HUBSPOT_DEAL_ID"):
            return "CHAT_WORKFLOW_E2E_HUBSPOT_DEAL_ID"
    return None


def evaluate_live_step_guard(
    plan: ConnectorActionPlan,
    *,
    options: LiveWorkflowOptions,
    client: Any,
    org_id: str,
    environment_name: str,
) -> tuple[StepLiveStatus, str | None]:
    if plan.destructive or _DELETE_ACTION.search(plan.invoke_action):
        if not options.allow_destructive:
            return "skipped", "Destructive action skipped (pass --allow-destructive)."

    if plan.kind != "write":
        return "passed", None

    if not options.enable_writes:
        return "skipped", "Write step skipped (pass --enable-writes)."

    from app.connectors.repository import get_connector_by_type

    connector = get_connector_by_type(client, org_id, plan.integration, environment_name=environment_name)
    if not _is_sandbox_write_allowed(
        environment_name=environment_name,
        connector=connector,
        env=options.env,
    ):
        return (
            "skipped",
            "Write skipped outside sandbox (use sandbox env, sandbox connector, or "
            "OAUTH_SMOKE_FORCE_SANDBOX_WRITES=1).",
        )

    missing = _missing_write_env(plan, options.env)
    if missing:
        return "blocked", f"Missing required env for live write: {missing}"

    return "passed", None


def sanitize_write_plan(
    plan: ConnectorActionPlan,
    *,
    run_tag: str,
    env: dict[str, str],
) -> ConnectorActionPlan:
    args = dict(plan.args)
    prefix = f"[{_WORKFLOW_PREFIX} {run_tag}]"

    if plan.invoke_action == "asana.tasks.create":
        name = str(args.get("name") or "Workflow task")
        args["name"] = f"{prefix} {name}"[:200]
    elif plan.invoke_action == "slack.post_message":
        channel = (
            env.get("CHAT_WORKFLOW_E2E_SLACK_CHANNEL")
            or env.get("OAUTH_SMOKE_SLACK_CHANNEL")
            or args.get("channel")
            or "general"
        )
        clean = str(channel).lstrip("#")
        message = str(args.get("message") or args.get("text") or "Workflow summary")
        body = f"{prefix} {message}"[:3000]
        args["channel"] = clean
        args["message"] = body
        args["text"] = body
    elif plan.invoke_action == "hubspot.contacts.create":
        email = f"gravitre-workflow-{run_tag}@example.com"
        props = dict(args.get("properties") or {})
        props.setdefault("firstname", "Gravitre")
        props.setdefault("lastname", f"Workflow-{run_tag[:8]}")
        props["email"] = email
        args["properties"] = props
        args["email"] = email
    elif plan.invoke_action in {"hubspot.deals.update", "hubspot.deals.update_stage"}:
        deal_id = env.get("CHAT_WORKFLOW_E2E_HUBSPOT_DEAL_ID")
        if deal_id:
            args["deal_id"] = deal_id
            args.setdefault("properties", {"notes_last_contacted": f"{prefix} smoke touch"})
    else:
        payload = dict(args.get("payload") or {})
        payload["workflow_e2e_tag"] = run_tag
        args["payload"] = payload

    return ConnectorActionPlan(
        tool_name=plan.tool_name,
        invoke_action=plan.invoke_action,
        integration=plan.integration,
        kind=plan.kind,
        label=plan.label,
        args=args,
        requires_approval=plan.requires_approval,
        approval_reason=plan.approval_reason,
        destructive=plan.destructive,
    )


def build_cleanup_record(
    plan: ConnectorActionPlan,
    *,
    run_tag: str,
    result: ExecutionResult,
    observation: dict[str, Any] | None,
) -> WorkflowCleanupRecord:
    data = observation.get("result") if isinstance(observation, dict) else None
    if not isinstance(data, dict):
        data = {}

    resource_id = str(result.entity_id or data.get("id") or data.get("gid") or "")
    resource_type = plan.integration

    if plan.invoke_action == "asana.tasks.create":
        task_id = str(data.get("gid") or data.get("data", {}).get("gid") or resource_id)
        return WorkflowCleanupRecord(
            integration="asana",
            invoke_action=plan.invoke_action,
            resource_type="task",
            resource_id=task_id,
            manual_instruction=f"Delete Asana task gid={task_id} tagged '{_WORKFLOW_PREFIX}'.",
            auto_cleanup_action="asana.tasks.delete",
        )
    if plan.invoke_action == "slack.post_message":
        ts = str(data.get("ts") or data.get("message", {}).get("ts") or "")
        channel = str(plan.args.get("channel") or "")
        return WorkflowCleanupRecord(
            integration="slack",
            invoke_action=plan.invoke_action,
            resource_type="message",
            resource_id=ts or channel,
            manual_instruction=(
                f"Remove Slack message ts={ts} in #{channel} containing '{_WORKFLOW_PREFIX} {run_tag}'."
            ),
            auto_cleanup_action=None,
        )
    if plan.invoke_action == "hubspot.contacts.create":
        contact_id = str(
            data.get("id")
            or data.get("contact", {}).get("id")
            or resource_id
        )
        email = plan.args.get("email") or plan.args.get("properties", {}).get("email")
        return WorkflowCleanupRecord(
            integration="hubspot",
            invoke_action=plan.invoke_action,
            resource_type="contact",
            resource_id=contact_id,
            manual_instruction=f"Archive/delete HubSpot contact id={contact_id} email={email}.",
            auto_cleanup_action="hubspot.contacts.delete",
        )
    if plan.invoke_action in {"hubspot.deals.update", "hubspot.deals.update_stage"}:
        deal_id = str(plan.args.get("deal_id") or resource_id)
        return WorkflowCleanupRecord(
            integration="hubspot",
            invoke_action=plan.invoke_action,
            resource_type="deal",
            resource_id=deal_id,
            manual_instruction=f"Review/revert HubSpot deal id={deal_id} touched by workflow E2E {run_tag}.",
            auto_cleanup_action=None,
        )

    return WorkflowCleanupRecord(
        integration=plan.integration,
        invoke_action=plan.invoke_action,
        resource_type=resource_type,
        resource_id=resource_id or run_tag,
        manual_instruction=f"Review {plan.invoke_action} side effects tagged '{_WORKFLOW_PREFIX} {run_tag}'.",
        auto_cleanup_action=None,
    )


def cleanup_instructions(records: list[WorkflowCleanupRecord]) -> list[str]:
    return [row.manual_instruction for row in records if row.manual_instruction]


@contextmanager
def _audit_event_tracker(client: Any, org_id: str, actor_id: str, bucket: list[dict[str, Any]]):
    from app.workflows.audit import write_audit_event as original

    def _tracking(
        audit_client: Any,
        audit_org: str,
        audit_actor: str,
        *,
        action: str,
        resource_type: str,
        resource_id: Any,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        original(
            audit_client,
            audit_org,
            audit_actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
        )
        if audit_org != org_id:
            return
        try:
            rows = (
                client.table("audit_events")
                .select("id, action, created_at")
                .eq("org_id", org_id)
                .eq("action", action)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                bucket.append({"id": str(rows[0]["id"]), "action": action})
        except Exception:  # noqa: BLE001
            bucket.append({"id": "", "action": action})

    with patch("app.services.tool_service.write_audit_event", side_effect=_tracking):
        with patch("app.workflows.audit.write_audit_event", side_effect=_tracking):
            yield bucket


@asynccontextmanager
async def live_orchestration_session(
    orchestration: ChatOrchestrationService,
    *,
    client: Any,
    org_id: str,
    user_id: str,
    environment_name: str,
    connected: list[str],
    options: LiveWorkflowOptions,
    run_id: str,
    step_records: list[WorkflowStepRecord],
    cleanup_records: list[WorkflowCleanupRecord],
    executed_actions: list[str],
    audit_events: list[str],
):
    connector = orchestration._connector
    run_tag = workflow_run_tag(run_id)
    last_observation: dict[str, Any | None] = {"value": None}
    audit_bucket: list[dict[str, Any]] = []

    original_execute_plan = connector.execute_plan
    original_execute_tool = connector._registry.execute_tool
    execute_counter = {"n": 0}

    async def _tracking_execute_tool(*, ctx, tool_name, args=None):
        with _audit_event_tracker(client, org_id, user_id, audit_bucket):
            observation = await original_execute_tool(ctx=ctx, tool_name=tool_name, args=args)
        last_observation["value"] = observation
        return observation

    async def _guarded_execute_plan(**kwargs):
        execute_counter["n"] += 1
        step_id = f"step_{execute_counter['n']}"
        plan: ConnectorActionPlan = kwargs["plan"]

        guard_status, guard_reason = evaluate_live_step_guard(
            plan,
            options=options,
            client=client,
            org_id=org_id,
            environment_name=environment_name,
        )

        if guard_status == "skipped":
            record = WorkflowStepRecord(
                step_id=step_id,
                invoke_action=plan.invoke_action,
                kind=plan.kind,
                status="skipped",
                request_payload=dict(plan.args),
                failure_reason=guard_reason,
            )
            step_records.append(record)
            executed_actions.append(plan.invoke_action)
            audit_events.append("tool.invoke.skipped")
            return ExecutionResult(
                success=True,
                entity_type="connector",
                entity_id="",
                url="/connectors",
                title=plan.label,
                body=guard_reason or "Step skipped.",
                task_label=plan.label,
            )

        if guard_status == "blocked":
            record = WorkflowStepRecord(
                step_id=step_id,
                invoke_action=plan.invoke_action,
                kind=plan.kind,
                status="blocked",
                request_payload=dict(plan.args),
                failure_reason=guard_reason,
            )
            step_records.append(record)
            executed_actions.append(plan.invoke_action)
            audit_events.append("tool.invoke.blocked")
            return ExecutionResult(
                success=False,
                entity_type="connector",
                entity_id="",
                url="/connectors",
                title=plan.label,
                body=guard_reason or "Step blocked.",
                task_label=plan.label,
            )

        exec_plan = plan
        if plan.kind == "write":
            exec_plan = sanitize_write_plan(plan, run_tag=run_tag, env=options.env)

        audit_bucket.clear()
        last_observation["value"] = None
        with _audit_event_tracker(client, org_id, user_id, audit_bucket):
            result = await original_execute_plan(**kwargs, plan=exec_plan)

        observation = last_observation["value"] if isinstance(last_observation["value"], dict) else {}
        event_ids = [str(row.get("id") or "") for row in audit_bucket if row.get("id")]
        for row in audit_bucket:
            audit_events.append(str(row.get("action") or "tool.invoke"))

        status: StepLiveStatus = "passed" if result.success else "failed"
        record = WorkflowStepRecord(
            step_id=step_id,
            invoke_action=plan.invoke_action,
            kind=plan.kind,
            status=status,
            request_payload=dict(exec_plan.args),
            response_shape=summarize_response_shape(observation.get("result")),
            audit_event_ids=[eid for eid in event_ids if eid],
            failure_reason=None if result.success else result.body,
        )
        step_records.append(record)
        executed_actions.append(plan.invoke_action)

        if result.success and exec_plan.kind == "write":
            cleanup_records.append(
                build_cleanup_record(
                    exec_plan,
                    run_tag=run_tag,
                    result=result,
                    observation=observation,
                )
            )
        return result

    async def _live_risk(*_args, **kwargs):
        plan = _args[2] if len(_args) > 2 else None
        requires = bool(getattr(plan, "kind", "") == "write" or getattr(plan, "destructive", False))
        return {
            "requires_approval": requires,
            "can_proceed_without_approval": not requires,
            "approval_reason": "Write action" if requires else None,
        }

    connector.execute_plan = _guarded_execute_plan  # type: ignore[method-assign]
    connector._registry.execute_tool = _tracking_execute_tool  # type: ignore[method-assign]

    with (
        patch.object(connector, "_verify_plan_executable", return_value=None),
        patch.object(connector, "_evaluate_risk", side_effect=_live_risk),
        patch("app.services.chat_orchestration_service.create_user_notification"),
        patch("app.services.chat_connector_execution_service.create_user_notification"),
    ):
        yield

    connector.execute_plan = original_execute_plan  # type: ignore[method-assign]
    connector._registry.execute_tool = original_execute_tool  # type: ignore[method-assign]


async def run_live_cleanup(
    *,
    client: Any,
    org_id: str,
    user_id: str,
    environment_name: str,
    options: LiveWorkflowOptions,
    records: list[WorkflowCleanupRecord],
) -> list[WorkflowCleanupRecord]:
    if not options.auto_cleanup:
        return records

    from app.config import get_settings
    from app.services.chat_connector_execution_service import get_chat_connector_execution_service
    from app.services.tool_registry import get_tool_registry
    from app.services.tool_service import ToolContext

    registry = get_tool_registry()
    connector_service = get_chat_connector_execution_service(get_settings())
    ctx = ToolContext(
        settings=get_settings(),
        client=client,
        org_id=org_id,
        actor_id=user_id,
        environment_name=environment_name,
    )
    updated: list[WorkflowCleanupRecord] = []
    for row in records:
        if not row.auto_cleanup_action:
            updated.append(row)
            continue
        if not options.allow_destructive:
            updated.append(
                WorkflowCleanupRecord(
                    integration=row.integration,
                    invoke_action=row.invoke_action,
                    resource_type=row.resource_type,
                    resource_id=row.resource_id,
                    manual_instruction=row.manual_instruction,
                    auto_cleanup_action=row.auto_cleanup_action,
                    auto_cleanup_status="skipped",
                    auto_cleanup_detail="Auto cleanup requires --allow-destructive.",
                )
            )
            continue
        args: dict[str, Any] = {}
        if row.auto_cleanup_action == "asana.tasks.delete":
            args["task_id"] = row.resource_id
        elif row.auto_cleanup_action == "hubspot.contacts.delete":
            args["contact_id"] = row.resource_id
        else:
            updated.append(row)
            continue
        try:
            tool_name = (
                connector_service._prefer_static_tool_name(row.auto_cleanup_action, row.integration)  # noqa: SLF001
                or row.auto_cleanup_action.replace(".", "_")
            )
            observation = await registry.execute_tool(
                ctx=ctx,
                tool_name=tool_name,
                args=args,
            )
            ok = bool(observation.get("success"))
            updated.append(
                WorkflowCleanupRecord(
                    integration=row.integration,
                    invoke_action=row.invoke_action,
                    resource_type=row.resource_type,
                    resource_id=row.resource_id,
                    manual_instruction=row.manual_instruction,
                    auto_cleanup_action=row.auto_cleanup_action,
                    auto_cleanup_status="passed" if ok else "failed",
                    auto_cleanup_detail=str(observation.get("error") or "Cleanup completed."),
                )
            )
        except Exception as exc:  # noqa: BLE001
            updated.append(
                WorkflowCleanupRecord(
                    integration=row.integration,
                    invoke_action=row.invoke_action,
                    resource_type=row.resource_type,
                    resource_id=row.resource_id,
                    manual_instruction=row.manual_instruction,
                    auto_cleanup_action=row.auto_cleanup_action,
                    auto_cleanup_status="failed",
                    auto_cleanup_detail=str(exc),
                )
            )
    return updated


def integration_label(integration: str) -> str:
    alias = INTEGRATION_ALIASES.get(integration, (integration.replace("_", " "),))
    return alias[0].title()
