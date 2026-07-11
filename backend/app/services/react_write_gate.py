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
    catalog_action_requires_write_approval,
    catalog_scopes_indicate_mutation,
)
from app.services.connector_action_workflows import format_write_approval_message
from app.services.event_intelligence_service import WRITE_ACTION_SUFFIXES

WRITE_APPROVAL_REQUIRED = "write_approval_required"

# Re-export for callers that imported helpers from this module.
__all__ = (
    "WRITE_APPROVAL_REQUIRED",
    "block_react_write_execution",
    "catalog_action_requires_write_approval",
    "catalog_scopes_indicate_mutation",
    "first_structured_connector_plan_from_react",
    "invoke_action_is_write",
    "materialize_react_write_approval_turn",
    "pending_write_from_react",
    "plan_from_react_tool_call",
    "plan_from_react_write",
    "tool_requires_user_write_approval",
)

# Extra write verbs not covered by EventIntelligence WRITE_ACTION_SUFFIXES.
# Used only as last-resort fallback when a registry tool is missing from the catalog.
_EXTRA_WRITE_SUFFIXES = (
    ".send",
    ".post_message",
    ".post",
    ".add",
    ".remove",
    ".subscribe",
    ".trigger",
    ".assign",
    ".transition",
    ".comment",
    ".acknowledge",
    ".resolve",
    ".reassign",
    ".escalate",
    ".add_note",
    ".update_stage",
    ".add_contact",
    ".add_project",
    ".add_member",
    ".add_contacts",
)


def invoke_action_is_write(invoke_action: str) -> bool:
    lowered = str(invoke_action or "").strip().lower()
    if not lowered:
        return False
    if any(lowered.endswith(suffix) for suffix in WRITE_ACTION_SUFFIXES):
        return True
    return any(lowered.endswith(suffix) for suffix in _EXTRA_WRITE_SUFFIXES)


def tool_requires_user_write_approval(tool_name: str, registry: Any) -> tuple[bool, str, str, str]:
    """Return (requires_approval, invoke_action, integration, label)."""
    name = str(tool_name or "").strip()
    if not name or name.startswith("assistant_") or name.startswith("mcp_"):
        return False, "", "", ""
    if name in {"web_search", "browser_agent_read", "browser_agent_interact", "knowledge_base"}:
        return False, "", "", ""

    spec = registry.get_spec(name) if registry is not None else None
    invoke_action = str(getattr(spec, "invoke_action", "") or "")
    integration = str(getattr(spec, "integration", "") or "")
    label = name.replace("_", " ")

    try:
        from app.services.connector_execution_matrix import build_connector_execution_matrix

        for entry in build_connector_execution_matrix():
            if entry.tool_registry_key != name:
                continue
            requires = catalog_action_requires_write_approval(
                kind=entry.kind,
                destructive=bool(entry.destructive),
                requires_approval=bool(entry.requires_approval),
                scopes=entry.required_scopes,
            )
            return (
                requires,
                entry.registry_key or entry.action_key or invoke_action,
                entry.connector_id or integration,
                entry.display_name or label,
            )
    except Exception:  # noqa: BLE001
        pass

    # Registry-only tools with no catalog row — last-resort suffix heuristic.
    if invoke_action and invoke_action_is_write(invoke_action):
        return True, invoke_action, integration, label
    return False, invoke_action, integration, label


def block_react_write_execution(
    tool_name: str,
    args: dict[str, Any] | None,
    registry: Any,
) -> dict[str, Any] | None:
    """If this ReAct tool call is a write, refuse execution and request approval."""
    requires, invoke_action, integration, label = tool_requires_user_write_approval(
        tool_name, registry
    )
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
                "args": dict(call.get("args") or result.get("args") or {}),
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
    approval = requires if requires_approval is None else bool(requires_approval)
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
    args = dict(pending.get("args") or result.get("args") or {})
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
            args = dict(result["args"])
        if not args and not result.get("pending_approval"):
            # No structured args to reuse — leave to NL mapper.
            continue
        plan = plan_from_react_tool_call(tool_name, args, registry)
        if plan is not None:
            return plan
    return None


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
    from app.services.tool_registry import get_tool_registry

    plan = plan_from_react_write(pending, get_tool_registry())
    if not plan:
        return None

    from app.services.chat_connector_execution_service import (
        ChatConnectorExecutionService,
        enrich_plan_inference_metadata,
    )
    from app.services.connector_parameter_inference import (
        ParameterInferenceContext,
        infer_missing_parameters,
    )
    from app.services.connector_session_state import load_connector_session
    from app.services.conversation_state_service import get_conversation_state_service

    # STA-305 — ReAct plans must carry the same inference metadata as governed chat.
    plan = enrich_plan_inference_metadata(plan, message=message or "")
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

    pending_params = {
        **ChatConnectorExecutionService.plan_to_dict(plan),
        "status": "awaiting_confirm",
        "source": "react_write_gate",
    }
    state = get_conversation_state_service(settings)
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
