"""ReAct-first connector routing — NL phrase mapper is fallback only."""
from __future__ import annotations

from typing import Any

PENDING_CONNECTOR_TASK_TYPES = frozenset({"connector_action", "connector_orchestration"})

_ASSISTANT_ONLY_TOOLS = frozenset(
    {
        "assistant_agent_status",
        "assistant_connector_status",
        "assistant_workflow_runs",
        "assistant_analytics",
        "assistant_generate_document",
        "assistant_run_agent_task",
        "assistant_create_workflow",
        "assistant_execute_workflow",
        "assistant_dependency_impact",
        "assistant_code_transform",
        "web_search",
        "knowledge_base",
    }
)


def has_pending_connector_task(task_state: dict[str, Any] | None) -> bool:
    pending = (task_state or {}).get("pending_task") or {}
    return str(pending.get("type") or "") in PENDING_CONNECTOR_TASK_TYPES


def _is_connector_tool_name(name: str) -> bool:
    if not name or name in _ASSISTANT_ONLY_TOOLS:
        return False
    if name.startswith("assistant_"):
        return False
    return True


def react_invoked_connector_tools(react_result: Any | None) -> bool:
    """True when ReAct attempted any connector tool (success or failure)."""
    if react_result is None:
        return False
    for call in react_result.tool_calls or []:
        name = str(call.get("tool") or call.get("name") or "")
        if _is_connector_tool_name(name):
            return True
    return False


def react_succeeded_connector_tools(react_result: Any | None) -> bool:
    """True when at least one connector tool call returned success=true."""
    if react_result is None:
        return False
    for call in react_result.tool_calls or []:
        name = str(call.get("tool") or call.get("name") or "")
        if not _is_connector_tool_name(name):
            continue
        result = call.get("result") if isinstance(call.get("result"), dict) else {}
        if result.get("success"):
            return True
    return False


def should_run_connector_preflight(
    task_state: dict[str, Any] | None,
    *,
    message: str = "",
    connected_integrations: list[str] | None = None,
    routing_tier: str | None = None,
) -> bool:
    """Run governed connector/orchestration resolution before clarification + ReAct.

    Pending connector tasks always preflight. Fresh *single*-connector intents still
    go to ReAct first (phrase-mapper via ``should_attempt_connector_fallback``).

    STA-307 — fresh *multi-step orchestration* intents also preflight so they are
    not swallowed by ``connector_unavailable`` clarify (which only names the first
    missing connector) and so zero-runnable plans reach terminal ``blocked``
    synchronously without a confirm/wait loop.

    STA-305 — omit-name list creates must *not* preflight as orchestration. A comma
    after the vendor name (e.g. \"In Apollo, create a contact list.\") falsely trips
    ``is_orchestration_intent``; the LIST_CREATE prefer_connector guard must live
    here as well as in ``run_connector_fallback_turn`` (parallel-path parity).
    """
    if has_pending_connector_task(task_state):
        return True
    if not (message or "").strip():
        return False
    from app.services.chat_connector_models import LIST_CREATE_INTENT
    from app.services.chat_orchestration_service import ChatOrchestrationService

    # Prefer governed single-connector auto-plan over multi-step orchestration.
    if LIST_CREATE_INTENT.search(message or ""):
        return False

    return ChatOrchestrationService.is_orchestration_intent(
        message,
        task_state or {},
        list(connected_integrations or []),
        routing_tier=routing_tier,
    )


async def run_connector_fallback_turn(
    *,
    settings: Any,
    org_id: str,
    user_id: str,
    conversation_id: str,
    message: str,
    classification: dict[str, Any],
    task_state: dict[str, Any],
    connected_integrations: list[str],
    client: Any,
    environment_name: str = "production",
    react_result: Any | None = None,
) -> dict[str, Any] | None:
    """After ReAct, try orchestration then governed connector path.

    Wave 1: when ReAct already produced structured connector tool_calls with args,
    pass those into ``process_turn`` so NL ``chat_action_mapper`` is skipped.
    """
    from app.services.chat_orchestration_service import (
        ChatOrchestrationService,
        get_chat_orchestration_service,
    )
    from app.services.react_write_gate import first_structured_connector_plan_from_react
    from app.services.tool_registry import get_tool_registry

    orchestration = get_chat_orchestration_service(settings)
    from app.services.chat_connector_models import LIST_CREATE_INTENT

    # STA-305 — omit-name list create must reach connector auto-plan, not multi-step
    # orchestration (comma after "Apollo," falsely trips is_orchestration_intent).
    prefer_connector = bool(LIST_CREATE_INTENT.search(message or ""))
    if (
        not prefer_connector
        and ChatOrchestrationService.is_orchestration_intent(
            message, task_state, connected_integrations
        )
    ):
        turn = await orchestration.process_turn(
            org_id=org_id,
            user_id=user_id,
            conversation_id=conversation_id,
            message=message,
            classification=classification,
            task_state=task_state,
            connected_integrations=connected_integrations,
            client=client,
            environment_name=environment_name,
        )
        if turn and turn.get("stop_pipeline"):
            return turn

    structured_plan = first_structured_connector_plan_from_react(
        react_result,
        get_tool_registry(),
    )
    # List-create intents must not inherit a ReAct read tool (lists.list / people.search)
    # as structured_plan — that bypasses write-gate staging.
    if (
        prefer_connector
        and structured_plan is not None
        and "lists.create" not in str(getattr(structured_plan, "invoke_action", "") or "").lower()
    ):
        structured_plan = None
    # Module B Phase 3 — ReAct and governed chat share one turn controller entry.
    from app.services.conversation_turn_controller import run_connector_turn

    turn = await run_connector_turn(
        settings=settings,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        message=message,
        classification=classification,
        task_state=task_state,
        connected_integrations=connected_integrations,
        client=client,
        environment_name=environment_name,
        structured_plan=structured_plan,
        source="react",
    )
    if turn and turn.get("stop_pipeline"):
        return turn
    return None


def should_attempt_connector_fallback(
    *,
    task_state: dict[str, Any] | None,
    react_result: Any | None,
    message: str,
    connected_integrations: list[str],
) -> bool:
    """After ReAct, try phrase mapper when connector tools were not successfully used.

    Failed ReAct connector attempts (e.g. synthetic-agent permission crashes) must
    still fall through to the governed approval/execute path — otherwise users see
    a generic connector execution error and never reach invoke_tool.
    """
    _ = connected_integrations  # retained for call-site compatibility
    from app.services.chat_connector_execution_service import ChatConnectorExecutionService
    from app.services.conversational_execution_service import CONFIRM_PATTERN, DECLINE_PATTERN

    from app.services.chat_message_normalize import strip_assistant_scope_prefix

    pending = has_pending_connector_task(task_state)
    text = strip_assistant_scope_prefix(message)
    # Pending confirm/decline must always reach process_turn — including when an
    # earlier org-scoped response cache or ReAct text path skipped preflight.
    if pending and (CONFIRM_PATTERN.match(text) or DECLINE_PATTERN.match(text)):
        return True
    if pending:
        return False
    if react_succeeded_connector_tools(react_result):
        return False

    if not ChatConnectorExecutionService.is_connector_intent(message, task_state or {}):
        return False
    return True
