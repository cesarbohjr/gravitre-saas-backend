"""Canonical frozen WRITE resume — confirm consumes the staged PendingAction.

LIVE must not re-plan or re-ask approval when a valid connector write is already
awaiting_confirm. Compose-only ExecutionPlan projections are not frozen writes.
"""
from __future__ import annotations

from typing import Any

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.conversational_execution_service import CONFIRM_PATTERN

_AWAITING = frozenset({"awaiting_confirm", "awaiting_admin_approval"})


def _pending_blob(task_state: dict[str, Any] | None) -> dict[str, Any]:
    state = task_state if isinstance(task_state, dict) else {}
    pending = state.get("pending_task")
    return pending if isinstance(pending, dict) else {}


def _pending_params(pending: dict[str, Any]) -> dict[str, Any]:
    params = pending.get("params")
    if isinstance(params, dict) and params:
        return params
    return pending


def frozen_connector_write_params(task_state: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return frozen connector WRITE params, or None if there is no executable pending."""
    pending = _pending_blob(task_state)
    if not pending:
        return None
    status = str(pending.get("status") or "").strip()
    if status not in _AWAITING:
        return None
    params = _pending_params(pending)
    invoke = str(params.get("invoke_action") or pending.get("invoke_action") or "").strip()
    kind = str(params.get("kind") or pending.get("kind") or "write").strip().lower()
    pending_type = str(pending.get("type") or "").strip()
    if not invoke:
        return None
    from app.services.action_lifecycle import existing_successful_write

    if existing_successful_write(task_state, invoke_action=invoke):
        return None
    if pending_type not in {"connector_action", "execution_plan_projection", ""}:
        return None
    if kind == "read":
        return None
    if pending_type == "execution_plan_projection" and not invoke:
        return None
    return {
        **params,
        "invoke_action": invoke,
        "integration": str(params.get("integration") or pending.get("connector_id") or "").strip(),
        "kind": kind or "write",
        "status": status,
        "type": "connector_action",
    }


def frozen_connector_write_plan(task_state: dict[str, Any] | None) -> ConnectorActionPlan | None:
    params = frozen_connector_write_params(task_state)
    if not params or not params.get("invoke_action"):
        return None
    from app.core.safe_dict import safe_normalize_stored_dict

    inferred = params.get("inferred_fields") or []
    return ConnectorActionPlan(
        tool_name=str(params.get("tool_name") or ""),
        invoke_action=str(params.get("invoke_action") or ""),
        integration=str(params.get("integration") or ""),
        kind=str(params.get("kind") or "write"),
        label=str(params.get("label") or ""),
        args=safe_normalize_stored_dict(params, key="args"),
        requires_approval=bool(params.get("requires_approval")),
        approval_reason=params.get("approval_reason"),
        destructive=bool(params.get("destructive")),
        inferred_fields=tuple(str(item) for item in inferred),
        inference_sources=safe_normalize_stored_dict(params, key="inference_sources"),
    )


def is_confirm_utterance(message: str) -> bool:
    return bool(CONFIRM_PATTERN.match((message or "").strip()))


def should_resume_frozen_write(message: str, task_state: dict[str, Any] | None) -> bool:
    return is_confirm_utterance(message) and frozen_connector_write_params(task_state) is not None


def should_skip_unified_live_for_compiled_write(
    message: str,
    task_state: dict[str, Any] | None,
    connected_integrations: list[str] | None,
) -> bool:
    """Keep HMAC/PendingAction/process_turn as the owner of governed writes."""
    from app.services.computer_browser_interact_turn import computer_interact_should_compile

    if computer_interact_should_compile(message, task_state):
        return True
    if should_resume_frozen_write(message, task_state):
        return True
    if is_confirm_utterance(message):
        return False
    connected = list(connected_integrations or [])
    if not connected:
        return False
    text = (message or "").strip()
    if len(text) < 12:
        return False
    from app.services.chat_orchestration_service import ChatOrchestrationService

    if ChatOrchestrationService.is_orchestration_intent(text, task_state or {}, connected):
        return False
    from app.services.chat_action_mapper import get_chat_action_mapper

    match = get_chat_action_mapper().match_segment(
        text, connected_integrations=connected
    )
    if match is None:
        return False
    entry = match.entry
    if str(entry.kind or "").lower() == "read":
        return False
    invoke = str(entry.registry_key or entry.action_key or "").strip()
    return bool(invoke)


async def resume_frozen_write_on_confirm(
    *,
    message: str,
    task_state: dict[str, Any] | None,
    org_id: str,
    user_id: str,
    conversation_id: str | None,
    client: Any,
    settings: Any,
    connected_integrations: list[str] | None = None,
    environment_name: str = "production",
    classification: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Consume the frozen pending WRITE via process_turn — do not compile a new ActionSpec."""
    if not should_resume_frozen_write(message, task_state):
        return None
    params = frozen_connector_write_params(task_state) or {}
    integration = str(params.get("integration") or "").strip()
    connected = list(connected_integrations or [])
    if integration and integration not in connected:
        connected = [*connected, integration]
    from app.services.chat_connector_execution_service import get_chat_connector_execution_service

    turn = await get_chat_connector_execution_service(settings).process_turn(
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id or "",
        message=message,
        classification=classification or {},
        task_state=dict(task_state or {}),
        connected_integrations=connected,
        client=client,
        environment_name=environment_name,
        pending_reply_intent="confirm",
    )
    if not isinstance(turn, dict):
        return None
    return turn
