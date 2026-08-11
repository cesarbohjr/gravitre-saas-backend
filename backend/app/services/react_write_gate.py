"""Block ReAct from executing connector writes without the chat approval gate.

Governed chat writes go through ``format_write_approval_message`` + ``awaiting_confirm``
before ``execute_plan`` → ``invoke_tool``. ReAct previously called ``execute_tool``
directly for writes (live 2026-07-10 apollo_lists_create), which is invoke_tool-governed
but not user-approval-governed. This module closes that gap.

Authority for “is this a write?” is the connector action catalog (kind + scopes +
destructive / requires_approval flags) — not a name-pattern early-return that treated
``kind=advanced`` as non-mutating and skipped the suffix fallback.
"""
from __future__ import annotations

from typing import Any

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.catalog_write_authority import (
    action_name_indicates_write,
    catalog_action_requires_write_approval,
    catalog_scopes_indicate_mutation,
    find_matrix_entry_for_tool_registry_key,
    invoke_action_requires_write_approval,
    matrix_entry_requires_write_approval,
)
from app.services.connector_action_workflows import format_write_approval_message
from app.core.safe_dict import safe_normalize_stored_dict

WRITE_APPROVAL_REQUIRED = "write_approval_required"

# Platform writes that must use the same chat approval gate as connector writes.
# Explicit allowlist (Wave 1 / PR #90 pattern) — not a blanket assistant_* skip.
PLATFORM_WRITE_TOOLS = frozenset(
    {
        "assistant_create_workflow",
        "assistant_execute_workflow",
        "assistant_run_agent_task",
    }
)

PLATFORM_PENDING_TASK_TYPES = frozenset(
    {
        "create_workflow",
        "execute_workflow",
        "run_agent_task",
    }
)

# Re-export for callers that imported helpers from this module.
__all__ = (
    "PLATFORM_PENDING_TASK_TYPES",
    "PLATFORM_WRITE_TOOLS",
    "WRITE_APPROVAL_REQUIRED",
    "block_react_write_execution",
    "catalog_action_requires_write_approval",
    "catalog_scopes_indicate_mutation",
    "first_structured_connector_plan_from_react",
    "invoke_action_is_write",
    "invoke_action_requires_write_approval",
    "materialize_react_platform_write_approval_turn",
    "materialize_react_write_approval_turn",
    "pending_write_from_react",
    "plan_from_react_tool_call",
    "plan_from_react_write",
    "resolve_user_write_approval_required",
    "tool_requires_user_write_approval",
)


def invoke_action_is_write(invoke_action: str) -> bool:
    """Backward-compatible alias — delegates to catalog_write_authority."""
    return action_name_indicates_write(invoke_action)


def tool_requires_user_write_approval(tool_name: str, registry: Any) -> tuple[bool, str, str, str]:
    """Return (is_write_action, invoke_action, integration, label).

    Catalog classification only — use ``resolve_user_write_approval_required`` when
    deciding whether to block execution for a specific user/org.
    """
    name = str(tool_name or "").strip()
    if not name:
        return False, "", "", ""
    if name.startswith("mcp_"):
        meta = None
        if registry is not None and hasattr(registry, "get_mcp_tool_meta"):
            meta = registry.get_mcp_tool_meta(name)
        if not isinstance(meta, dict):
            return False, f"mcp.{name}", "mcp", name.replace("mcp_", "").replace("_", " ")
        from app.services.catalog_write_authority import mcp_tool_requires_write_approval

        requires = mcp_tool_requires_write_approval(
            capability_tier=str(meta.get("capability_tier") or "") or None,
            requires_approval=meta.get("requires_approval"),
            read_only_hint=meta.get("read_only_hint"),
            destructive_hint=meta.get("destructive_hint"),
        )
        label = str(meta.get("label") or meta.get("description") or name)
        return requires, f"mcp.{name}", "mcp", label
    if name in {"web_search", "browser_agent_read", "browser_agent_interact", "knowledge_base"}:
        return False, "", "", ""

    spec = registry.get_spec(name) if registry is not None else None
    invoke_action = str(getattr(spec, "invoke_action", "") or "")
    integration = str(getattr(spec, "integration", "") or "")
    label = name.replace("_", " ")

    # Platform writes: explicit allowlist (do not rely on suffix heuristics —
    # assistant.create_workflow / .execute_workflow / .run_agent_task would miss).
    if name in PLATFORM_WRITE_TOOLS:
        if not invoke_action and spec is not None:
            invoke_action = str(getattr(spec, "invoke_action", "") or "")
        if not invoke_action:
            invoke_action = f"assistant.{name.removeprefix('assistant_')}"
        if not integration:
            integration = "platform"
        if name == "assistant_create_workflow":
            label = "Create workflow"
        elif name == "assistant_execute_workflow":
            label = "Execute workflow"
        elif name == "assistant_run_agent_task":
            label = "Run agent task"
        return True, invoke_action, integration, label

    # Remaining assistant_* tools are read/status helpers — never gated.
    if name.startswith("assistant_"):
        return False, "", "", ""

    entry = find_matrix_entry_for_tool_registry_key(name)
    if entry is not None:
        requires = matrix_entry_requires_write_approval(entry)
        return (
            requires,
            entry.registry_key or entry.action_key or invoke_action,
            entry.connector_id or integration,
            entry.display_name or label,
        )

    # Registry-only tools with no catalog row — last-resort via shared authority.
    if invoke_action and invoke_action_requires_write_approval(invoke_action):
        return True, invoke_action, integration, label
    return False, invoke_action, integration, label


def resolve_user_write_approval_required(
    client: Any,
    org_id: str,
    user_id: str,
    tool_name: str,
    registry: Any,
    *,
    settings: Any | None = None,
) -> tuple[bool, str, str, str]:
    """Return (requires_user_approval, invoke_action, integration, label)."""
    is_write, invoke_action, integration, label = tool_requires_user_write_approval(
        tool_name, registry
    )
    if not is_write:
        return False, invoke_action, integration, label
    if client is None or not str(org_id or "").strip() or not str(user_id or "").strip():
        return False, invoke_action, integration, label

    from app.services.hitl_policy_service import classify_action_kind, get_hitl_policy_service

    action_kind = classify_action_kind(
        invoke_action=invoke_action,
        tool_name=tool_name,
        label=label,
    )
    decision = get_hitl_policy_service(settings).resolve(
        client,
        org_id=str(org_id),
        user_id=str(user_id),
        action_kind=action_kind,
    )
    return bool(decision.requires_approval), invoke_action, integration, label


def block_react_write_execution(
    tool_name: str,
    args: dict[str, Any] | None,
    registry: Any,
    *,
    client: Any = None,
    org_id: str | None = None,
    user_id: str | None = None,
    settings: Any | None = None,
) -> dict[str, Any] | None:
    """If this ReAct tool call needs user approval per HITL policy, block execution."""
    if client is not None and org_id and user_id:
        requires, invoke_action, integration, label = resolve_user_write_approval_required(
            client,
            org_id,
            user_id,
            tool_name,
            registry,
            settings=settings,
        )
    else:
        requires, invoke_action, integration, label = tool_requires_user_write_approval(
            tool_name, registry
        )
        requires = False
    if not requires:
        return None
    raw_args = dict(args or {})
    # Explicit approval tokens are reserved for Approvals-queue / future wiring —
    # chat confirmation uses pending_task, not a model-supplied approval_id.
    raw_args.pop("approval_id", None)
    raw_args.pop("approvalId", None)
    return {
        "success": False,
        "tool": tool_name,
        "action": invoke_action,
        "integration": integration,
        "label": label,
        "pending_approval": True,
        "error_code": WRITE_APPROVAL_REQUIRED,
        "error": (
            "Write actions require explicit user approval before execution. "
            "Do not retry this tool; the user will confirm or edit the plan."
        ),
        "args": raw_args,
    }


def pending_write_from_react(react_result: Any | None) -> dict[str, Any] | None:
    """Return the first ReAct tool call blocked for write approval."""
    if react_result is None:
        return None
    for call in react_result.tool_calls or []:
        result = call.get("result") if isinstance(call.get("result"), dict) else {}
        if result.get("pending_approval") and result.get("error_code") == WRITE_APPROVAL_REQUIRED:
            return {
                "tool": str(call.get("tool") or call.get("name") or result.get("tool") or ""),
                "args": safe_normalize_stored_dict(call, key='args') or safe_normalize_stored_dict(result, key='args'),
                "result": result,
            }
    return None


def plan_from_react_tool_call(
    tool_name: str,
    args: dict[str, Any] | None,
    registry: Any,
    *,
    requires_approval: bool | None = None,
) -> ConnectorActionPlan | None:
    """Build a ConnectorActionPlan from a structured ReAct tool call (Wave 1).

    Prefer this over NL ``chat_action_mapper`` whenever ReAct already produced
    typed tool_calls with args.
    """
    name = str(tool_name or "").strip()
    if not name:
        return None
    requires, invoke_action, integration, label = tool_requires_user_write_approval(name, registry)
    if not invoke_action:
        spec = registry.get_spec(name) if registry is not None else None
        invoke_action = str(getattr(spec, "invoke_action", "") or "")
        integration = str(getattr(spec, "integration", "") or integration)
        label = label or name.replace("_", " ")
    if not invoke_action:
        return None
    if not integration and "." in invoke_action:
        integration = invoke_action.split(".", 1)[0]
    kind = "write" if (requires or invoke_action_is_write(invoke_action)) else "read"
    approval = bool(requires_approval) if requires_approval is not None else False
    return ConnectorActionPlan(
        tool_name=name,
        invoke_action=invoke_action,
        integration=integration or "connector",
        kind=kind,
        label=label or name.replace("_", " "),
        args=dict(args or {}),
        requires_approval=approval,
        approval_reason="react_structured_tool_call" if approval else None,
        destructive=False,
    )


def plan_from_react_write(pending: dict[str, Any], registry: Any | None = None) -> ConnectorActionPlan | None:
    result = pending.get("result") if isinstance(pending.get("result"), dict) else {}
    tool_name = str(pending.get("tool") or result.get("tool") or "").strip()
    args = safe_normalize_stored_dict(pending, key='args') or safe_normalize_stored_dict(result, key='args')
    if registry is not None:
        plan = plan_from_react_tool_call(tool_name, args, registry, requires_approval=True)
        if plan is not None:
            # Preserve gate metadata when present.
            invoke_action = str(result.get("action") or plan.invoke_action)
            integration = str(result.get("integration") or plan.integration)
            label = str(result.get("label") or plan.label)
            return ConnectorActionPlan(
                tool_name=plan.tool_name,
                invoke_action=invoke_action,
                integration=integration,
                kind="write",
                label=label,
                args=plan.args,
                requires_approval=True,
                approval_reason="react_write_gate",
                destructive=False,
            )
    # Fallback when registry is unavailable (unit tests / early boot).
    invoke_action = str(result.get("action") or "").strip()
    integration = str(result.get("integration") or "").strip()
    label = str(result.get("label") or "").strip() or tool_name.replace("_", " ")
    if not tool_name or not invoke_action:
        return None
    if not integration and "." in invoke_action:
        integration = invoke_action.split(".", 1)[0]
    return ConnectorActionPlan(
        tool_name=tool_name,
        invoke_action=invoke_action,
        integration=integration or "connector",
        kind="write",
        label=label,
        args=args,
        requires_approval=True,
        approval_reason="react_write_gate",
        destructive=False,
    )


def first_structured_connector_plan_from_react(
    react_result: Any | None,
    registry: Any,
) -> ConnectorActionPlan | None:
    """Prefer the first connector tool_call with args for governed fallback (no NL)."""
    if react_result is None:
        return None
    for call in react_result.tool_calls or []:
        if not isinstance(call, dict):
            continue
        tool_name = str(call.get("tool") or call.get("name") or "").strip()
        if not tool_name or tool_name.startswith("assistant_") or tool_name in {
            "web_search",
            "knowledge_base",
            "browser_agent_read",
            "browser_agent_interact",
        }:
            continue
        args = call.get("args") if isinstance(call.get("args"), dict) else {}
        result = call.get("result") if isinstance(call.get("result"), dict) else {}
        if not args and isinstance(result.get("args"), dict):
            args = safe_normalize_stored_dict(result, key="args")
        if not args and not result.get("pending_approval"):
            # No structured args to reuse — leave to NL mapper.
            continue
        plan = plan_from_react_tool_call(tool_name, args, registry)
        if plan is not None:
            return plan
    return None


def _resolve_workflow_for_approval(
    client: Any,
    org_id: str,
    *,
    query: str,
    workflow_id: str | None = None,
) -> dict[str, Any] | None:
    """Resolve a workflow row for execute approval copy (name/goal/id)."""
    from app.workflows.repository import list_workflows

    workflows = list_workflows(client, org_id)
    wf_id = str(workflow_id or "").strip()
    if wf_id:
        for row in workflows:
            if str(row.get("id") or "") == wf_id:
                return dict(row)
    needle = str(query or "").strip().lower()
    if not needle:
        return None
    for row in workflows:
        row_id = str(row.get("id") or "")
        name = str(row.get("name") or "").lower()
        if row_id == needle or (name and name in needle) or (needle and needle in name):
            return dict(row)
    return None


def _resolve_agent_for_approval(
    client: Any,
    org_id: str,
    *,
    task: str,
    agent_id: str | None = None,
) -> dict[str, Any] | None:
    from app.services.assistant_tools import _resolve_agent_for_task

    return _resolve_agent_for_task(client, org_id, task, agent_id=agent_id)


async def materialize_react_platform_write_approval_turn(
    *,
    settings: Any,
    org_id: str,
    conversation_id: str,
    client: Any,
    react_result: Any,
    message: str = "",
    environment_name: str = "production",
) -> dict[str, Any] | None:
    """Persist platform pending_task (create/execute/run) — not connector_action shape."""
    pending = pending_write_from_react(react_result)
    if not pending or not conversation_id:
        return None
    tool = str(pending.get("tool") or "").strip()
    if tool not in PLATFORM_WRITE_TOOLS:
        return None
    args = safe_normalize_stored_dict(pending, key='args')
    result = pending.get("result") if isinstance(pending.get("result"), dict) else {}
    if not args and isinstance(result.get("args"), dict):
        args = safe_normalize_stored_dict(result, key="args")

    from app.services.conversation_state_service import get_conversation_state_service

    state = get_conversation_state_service(settings)

    if tool == "assistant_create_workflow":
        goal = str(args.get("goal") or args.get("name") or message or "Assistant workflow").strip()
        name = str(args.get("name") or "").strip()
        clarified = {
            "workflow_goal": goal,
            **({"workflow_name": name} if name else {}),
            "source": "react_write_gate",
            "tool_name": tool,
            "invoke_action": "assistant.create_workflow",
        }
        task_type = "create_workflow"
        confirm_message = (
            f"I'll create a draft workflow for **{goal}**.\n\n"
            "Reply **yes** to create it now, or tell me what to adjust."
        )
    elif tool == "assistant_execute_workflow":
        query = str(args.get("query") or args.get("workflowId") or message or "").strip()
        workflow_id_arg = str(args.get("workflowId") or args.get("workflow_id") or "").strip() or None
        match = _resolve_workflow_for_approval(
            client, org_id, query=query, workflow_id=workflow_id_arg
        )
        if not match:
            return {
                "stop_pipeline": True,
                "dialogue_mode": "clarify",
                "message": (
                    "I need a specific workflow to execute. "
                    "Name the workflow exactly, or open Workflows and paste its id."
                ),
                "task_state": await state.get_task_state(conversation_id, org_id, client=client),
                "pending_task": None,
            }
        wf_id = str(match.get("id") or "")
        wf_name = str(match.get("name") or "Workflow")
        wf_goal = str(match.get("goal") or match.get("description") or "").strip()
        clarified = {
            "query": query or wf_name,
            "workflow_id": wf_id,
            "workflow_name": wf_name,
            "workflow_goal": wf_goal or None,
            "environment_name": environment_name,
            "source": "react_write_gate",
            "tool_name": tool,
            "invoke_action": "assistant.execute_workflow",
        }
        task_type = "execute_workflow"
        goal_line = f"\nGoal: {wf_goal}" if wf_goal else ""
        confirm_message = (
            f"I'll **execute** the workflow **{wf_name}** "
            f"(id `{wf_id}`).{goal_line}\n\n"
            "This starts a new run and may trigger connected steps "
            "(connectors, agents, notifications).\n\n"
            "Reply **yes** to run it now, or **no** to cancel."
        )
    else:  # assistant_run_agent_task
        task = str(args.get("task") or message or "").strip()
        agent_id_arg = str(args.get("agentId") or args.get("agent_id") or "").strip() or None
        agent = _resolve_agent_for_approval(client, org_id, task=task, agent_id=agent_id_arg)
        if not agent or not task:
            return {
                "stop_pipeline": True,
                "dialogue_mode": "clarify",
                "message": (
                    "I need an agent and a task before I can run anything. "
                    "Name the agent and describe the task."
                ),
                "task_state": await state.get_task_state(conversation_id, org_id, client=client),
                "pending_task": None,
            }
        agent_id = str(agent.get("id") or "")
        agent_name = str(agent.get("name") or "Agent")
        clarified = {
            "task": task,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "source": "react_write_gate",
            "tool_name": tool,
            "invoke_action": "assistant.run_agent_task",
        }
        task_type = "run_agent_task"
        truncated = task if len(task) <= 240 else task[:237] + "..."
        confirm_message = (
            f"I'll run **{agent_name}** on this task:\n\n> {truncated}\n\n"
            "The agent may use its permitted tools and connected integrations "
            "(including writes).\n\n"
            "Reply **yes** to start, or **no** to cancel."
        )

    await state.update_task_state(
        conversation_id,
        org_id,
        {
            "clarified_params": clarified,
            "pending_task": {
                "type": task_type,
                "status": "awaiting_confirm",
                "params": clarified,
            },
        },
        client=client,
    )
    refreshed = await state.get_task_state(conversation_id, org_id, client=client)
    return {
        "stop_pipeline": True,
        "dialogue_mode": "confirm",
        "message": confirm_message,
        "task_state": refreshed,
        "pending_task": refreshed.get("pending_task"),
    }


async def materialize_react_write_approval_turn(
    *,
    settings: Any,
    org_id: str,
    conversation_id: str,
    client: Any,
    react_result: Any,
    message: str = "",
    task_state: dict[str, Any] | None = None,
    environment_name: str = "production",
) -> dict[str, Any] | None:
    """Persist awaiting_confirm + return the same approval UX as governed chat writes."""
    pending = pending_write_from_react(react_result)
    if not pending or not conversation_id:
        return None

    tool = str(pending.get("tool") or "").strip()
    pending_args = safe_normalize_stored_dict(pending, key='args')
    pending_result = pending.get("result") if isinstance(pending.get("result"), dict) else {}
    pending_invoke = str(pending_result.get("action") or "").strip() or None
    from app.services.chat_write_intent import evaluate_connector_tool_proposal

    review = evaluate_connector_tool_proposal(
        message=message or "",
        tool_name=tool,
        invoke_action=pending_invoke,
        args=pending_args,
    )
    if review.action == "clarify":
        from app.services.conversation_state_service import get_conversation_state_service

        state = get_conversation_state_service(settings)
        refreshed = await state.get_task_state(conversation_id, org_id, client=client)
        return {
            "stop_pipeline": True,
            "dialogue_mode": "clarify",
            "message": review.clarify_message,
            "task_state": refreshed,
            "pending_task": None,
        }

    if tool in PLATFORM_WRITE_TOOLS:
        return await materialize_react_platform_write_approval_turn(
            settings=settings,
            org_id=org_id,
            conversation_id=conversation_id,
            client=client,
            react_result=react_result,
            message=message,
            environment_name=environment_name,
        )

    from app.services.tool_registry import get_tool_registry

    plan = plan_from_react_write(pending, get_tool_registry())
    if not plan:
        return None

    from app.services.chat_connector_execution_service import (
        ChatConnectorExecutionService,
        enrich_plan_inference_metadata,
    )
    from app.services.connector_action_workflows import (
        missing_params_stage_patch,
        scrub_gmail_write_plan,
    )
    from app.services.connector_parameter_inference import (
        ParameterInferenceContext,
        infer_missing_parameters,
    )
    from app.services.connector_session_state import load_connector_session
    from app.services.conversation_state_service import get_conversation_state_service
    from app.services.pack_common_intent_defaults import apply_pack_common_defaults

    # STA-305 — ReAct plans must carry the same inference metadata as governed chat.
    plan = enrich_plan_inference_metadata(plan, message=message or "")
    plan = apply_pack_common_defaults(plan, message=message or "")
    inference_context = ParameterInferenceContext(
        message=message or "",
        conversation_history=list((task_state or {}).get("recent_user_messages") or []),
        task_state=task_state or {},
        connector_session=load_connector_session(task_state or {}),
        client=client,
        org_id=org_id,
        settings=settings,
        environment_name=environment_name,
    )
    plan = infer_missing_parameters(plan, inference_context)
    plan = scrub_gmail_write_plan(plan)

    state = get_conversation_state_service(settings)
    # Dual-path SoT with classical chat / unified-turn: clarify before confirm.
    staged_missing = missing_params_stage_patch(
        plan, message or "", task_state=task_state or {}
    )
    if staged_missing:
        clarification, stage_patch = staged_missing
        await state.update_task_state(
            conversation_id,
            org_id,
            {**stage_patch, "recent_user_messages": [message or ""]},
            client=client,
        )
        refreshed = await state.get_task_state(conversation_id, org_id, client=client)
        return {
            "stop_pipeline": True,
            "dialogue_mode": clarification.dialogue_mode or "clarify",
            "message": clarification.message,
            "task_state": refreshed,
            "pending_task": refreshed.get("pending_task"),
            "workflow_status": clarification.status,
        }

    pending_params = {
        **ChatConnectorExecutionService.plan_to_dict(plan),
        "status": "awaiting_confirm",
        "source": "react_write_gate",
    }
    await state.update_task_state(
        conversation_id,
        org_id,
        {
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_confirm",
                "params": pending_params,
            }
        },
        client=client,
    )
    refreshed = await state.get_task_state(conversation_id, org_id, client=client)
    return {
        "stop_pipeline": True,
        "dialogue_mode": "confirm",
        "message": format_write_approval_message(plan),
        "task_state": refreshed,
        "pending_task": refreshed.get("pending_task"),
    }
