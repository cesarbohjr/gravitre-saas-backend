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
        "web_search",
        "knowledge_base",
    }
)


def has_pending_connector_task(task_state: dict[str, Any] | None) -> bool:
    pending = (task_state or {}).get("pending_task") or {}
    return str(pending.get("type") or "") in PENDING_CONNECTOR_TASK_TYPES


def react_invoked_connector_tools(react_result: Any | None) -> bool:
    if react_result is None:
        return False
    for call in react_result.tool_calls or []:
        name = str(call.get("tool") or call.get("name") or "")
        if not name or name in _ASSISTANT_ONLY_TOOLS:
            continue
        if name.startswith("assistant_"):
            continue
        return True
    return False


def should_run_connector_preflight(
    task_state: dict[str, Any] | None,
    *,
    message: str = "",
) -> bool:
    """Run governed connector resolution before ReAct for in-flight or fresh connector intents."""
    if has_pending_connector_task(task_state):
        return True
    text = message.strip()
    if not text:
        return False
    from app.services.chat_connector_execution_service import ChatConnectorExecutionService

    return ChatConnectorExecutionService.is_connector_intent(text, task_state or {})


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
) -> dict[str, Any] | None:
    """After ReAct, try orchestration then phrase mapper when the model did not call connector tools."""
    from app.services.chat_connector_execution_service import get_chat_connector_execution_service
    from app.services.chat_orchestration_service import (
        ChatOrchestrationService,
        get_chat_orchestration_service,
    )

    orchestration = get_chat_orchestration_service(settings)
    if ChatOrchestrationService.is_orchestration_intent(message, task_state, connected_integrations):
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

    connector = get_chat_connector_execution_service(settings)
    turn = await connector.process_turn(
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
    return None


def should_attempt_connector_fallback(
    *,
    task_state: dict[str, Any] | None,
    react_result: Any | None,
    message: str,
    connected_integrations: list[str],
) -> bool:
    """After ReAct, try phrase mapper when the model did not invoke connector tools."""
    if has_pending_connector_task(task_state):
        return False
    if react_invoked_connector_tools(react_result):
        return False
    from app.services.chat_connector_execution_service import ChatConnectorExecutionService

    if not ChatConnectorExecutionService.is_connector_intent(message, task_state or {}):
        return False
    return True
