"""Conversation Turn Controller (Module B Phases 3–4).

One shared entry before connector-specific logic: ledger ingest, awaiting_params
resume, schema extraction, and pending-plan recovery. Governed chat, ReAct, and
canvas NL→args enter here. Meson UI stays separate; Meson reasoning migrates later.

Module D (gravitree_voice): this controller is the ownership point for
connector-turn user-facing strings. Surfaces must not invent per-connector tone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.gravitree_voice import format_operator_message, voice_system_prompt_section
from app.services.parameter_ledger import (
    ParameterLedger,
    get_ledger,
    ingest_message_slots,
    is_awaiting_params,
    ledger_patch,
)

logger = get_logger(__name__)

PendingPlanIntent = Literal["continue", "modify", "cancel", "unclear"]


class PendingPlanIntentResult(BaseModel):
    intent: PendingPlanIntent = "unclear"
    reason: str = ""


@dataclass
class TurnInterpretation:
    """Shared turn context produced before connector / ReAct / canvas branching."""

    message: str
    task_state: dict[str, Any]
    ledger: ParameterLedger
    awaiting_params: bool = False
    pending_confirm: bool = False
    has_current_plan: bool = False
    pending_plan_intent: PendingPlanIntent | None = None
    structured_plan: ConnectorActionPlan | None = None
    source: str = "chat"
    voice_section: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


async def prepare_conversation_turn(
    *,
    message: str,
    org_id: str,
    conversation_id: str,
    task_state: dict[str, Any] | None,
    client: Any = None,
    settings: Settings | None = None,
    source: str = "chat",
    structured_plan: ConnectorActionPlan | None = None,
    persist: bool = True,
) -> TurnInterpretation:
    """Load ledger, ingest this turn's slots, classify pending-plan recovery."""
    from app.services.chat_message_normalize import strip_assistant_scope_prefix
    from app.services.conversation_state_service import get_conversation_state_service

    text = strip_assistant_scope_prefix(message or "")
    state = dict(task_state or {})
    turn_index = len(list(state.get("recent_user_messages") or [])) + 1
    ledger = ingest_message_slots(text, turn_index=turn_index, ledger=get_ledger(state))
    state = {**state, **ledger_patch(ledger)}

    if persist and conversation_id and org_id:
        try:
            await get_conversation_state_service(settings or get_settings()).update_task_state(
                conversation_id,
                org_id,
                {**ledger_patch(ledger), "recent_user_messages": [text]},
                client=client,
            )
            state = await get_conversation_state_service(settings or get_settings()).get_task_state(
                conversation_id, org_id, client=client
            )
            ledger = get_ledger(state)
        except Exception as exc:  # noqa: BLE001
            logger.debug("turn controller ledger persist skipped: %s", exc)

    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}
    pending_status = str(pending.get("status") or "")
    current_plan = state.get("current_plan") if isinstance(state.get("current_plan"), dict) else None
    # Module B — terminal orch + sticky plan must not accept a later bare "yes".
    if pending_status in {"completed", "failed", "cancelled"}:
        if persist and conversation_id and org_id:
            try:
                await get_conversation_state_service(settings or get_settings()).update_task_state(
                    conversation_id,
                    org_id,
                    {
                        "pending_task": None,
                        "current_plan": None,
                        "clarified_params": {},
                        "pending_steps": [],
                        "completed_steps": [],
                    },
                    client=client,
                )
                state = await get_conversation_state_service(
                    settings or get_settings()
                ).get_task_state(conversation_id, org_id, client=client)
            except Exception:  # noqa: BLE001
                logger.debug("terminal_orch_close_skipped", exc_info=True)
        current_plan = None
        pending = {}
        pending_status = ""
    voice_section = voice_system_prompt_section()

    pending_intent: PendingPlanIntent | None = None
    if current_plan or pending_status in {
        "awaiting_confirm",
        "awaiting_plan_confirm",
        "awaiting_admin_approval",
        "awaiting_step_confirm",
    }:
        pending_intent = await classify_pending_plan_intent(
            text,
            current_plan=current_plan,
            pending_task=pending if pending else None,
            settings=settings,
        )
        # Unrelated intervening turn — archive sticky advisory plan.
        if pending_intent == "unclear" and current_plan and persist:
            try:
                from app.services.conversation_state_service import get_conversation_state_service

                await get_conversation_state_service(settings or get_settings()).update_task_state(
                    conversation_id,
                    org_id,
                    {"current_plan": None, "pending_steps": [], "completed_steps": []},
                    client=client,
                )
                current_plan = None
            except Exception:  # noqa: BLE001
                logger.debug("stale_plan_supersede_skipped", exc_info=True)

    return TurnInterpretation(
        message=text,
        task_state=state,
        ledger=ledger,
        awaiting_params=is_awaiting_params(state),
        pending_confirm=pending_status
        in {"awaiting_confirm", "awaiting_plan_confirm", "awaiting_admin_approval"},
        has_current_plan=bool(current_plan),
        pending_plan_intent=pending_intent,
        structured_plan=structured_plan,
        source=source,
        voice_section=voice_section,
    )


async def classify_pending_plan_intent(
    message: str,
    *,
    current_plan: dict[str, Any] | None = None,
    pending_task: dict[str, Any] | None = None,
    settings: Settings | None = None,
    org_id: str | None = None,
    use_model: bool = True,
) -> PendingPlanIntent:
    """FAST-tier continue/modify/cancel for pending plans (Module B Phase 4)."""
    from app.services.conversational_execution_service import CONFIRM_PATTERN, DECLINE_PATTERN

    import re

    text = (message or "").strip()
    if not text:
        return "unclear"
    if DECLINE_PATTERN.match(text) or re.search(
        r"\b(cancel|never\s*mind|abort|stop\s+(?:that|this|the\s+plan))\b",
        text,
        re.I,
    ):
        return "cancel"
    if CONFIRM_PATTERN.match(text) or text.lower() in {"yes", "y", "ok", "okay", "confirm"}:
        return "continue"

    # Off-script but reasonable: skip/modify language without hard cancel.
    if re_modify_hint(text):
        if use_model:
            model_intent = await _model_pending_intent(
                text,
                current_plan=current_plan,
                pending_task=pending_task,
                settings=settings,
                org_id=org_id,
            )
            if model_intent in {"continue", "modify", "cancel"}:
                return model_intent  # type: ignore[return-value]
        return "modify"

    if use_model and (current_plan or pending_task):
        model_intent = await _model_pending_intent(
            text,
            current_plan=current_plan,
            pending_task=pending_task,
            settings=settings,
            org_id=org_id,
        )
        if model_intent in {"continue", "modify", "cancel"}:
            return model_intent  # type: ignore[return-value]

    return "unclear"


def re_modify_hint(text: str) -> bool:
    import re

    return bool(
        re.search(
            r"\b(skip|instead|just|only|change|modify|rather|don't|dont|without|"
            r"forget\s+step|go\s+straight|create\s+the\s+list)\b",
            text,
            re.I,
        )
    )


async def _model_pending_intent(
    message: str,
    *,
    current_plan: dict[str, Any] | None,
    pending_task: dict[str, Any] | None,
    settings: Settings | None,
    org_id: str | None,
) -> PendingPlanIntent:
    try:
        from app.services.model_router import TaskType, get_model_router

        goal = ""
        if isinstance(current_plan, dict):
            goal = str(current_plan.get("goal") or current_plan.get("summary") or "")[:300]
        pending_type = ""
        if isinstance(pending_task, dict):
            pending_type = str(pending_task.get("type") or pending_task.get("status") or "")
        prompt = (
            "Classify the user reply about a pending assistant plan.\n"
            "Labels: continue (approve/proceed), modify (change steps/skip/alter), "
            "cancel (abort), unclear.\n\n"
            f"Pending plan goal: {goal or '(none)'}\n"
            f"Pending task: {pending_type or '(none)'}\n"
            f"User reply: {message}\n"
        )
        response = await get_model_router(settings or get_settings()).complete(
            task_type=TaskType.CLASSIFICATION,
            prompt=prompt,
            system_prompt=(
                'Respond as JSON: {"intent":"continue|modify|cancel|unclear","reason":"..."}'
            ),
            temperature=0.0,
            max_tokens=80,
            response_format=PendingPlanIntentResult,
            org_id=org_id,
        )
        parsed = response.parsed if isinstance(response.parsed, dict) else None
        if not parsed:
            import json

            try:
                parsed = json.loads(response.content or "{}")
            except Exception:  # noqa: BLE001
                return "unclear"
        intent = str((parsed or {}).get("intent") or "unclear").lower().strip()
        if intent in {"continue", "modify", "cancel", "unclear"}:
            return intent  # type: ignore[return-value]
    except Exception as exc:  # noqa: BLE001
        logger.debug("pending plan intent model skipped: %s", exc)
    return "unclear"


async def run_connector_turn(
    *,
    settings: Settings | None,
    org_id: str,
    user_id: str,
    conversation_id: str,
    message: str,
    classification: dict[str, Any],
    task_state: dict[str, Any],
    connected_integrations: list[str],
    client: Any,
    environment_name: str = "production",
    structured_plan: ConnectorActionPlan | None = None,
    source: str = "chat",
) -> dict[str, Any] | None:
    """Shared connector turn entry for governed chat and ReAct fallback."""
    from app.services.chat_connector_execution_service import get_chat_connector_execution_service

    interpretation = await prepare_conversation_turn(
        message=message,
        org_id=org_id,
        conversation_id=conversation_id,
        task_state=task_state,
        client=client,
        settings=settings,
        source=source,
        structured_plan=structured_plan,
        persist=True,
    )

    # Phase 4 — modify/cancel pending strategic plans instead of stalling on CONFIRM_PATTERN.
    if interpretation.pending_plan_intent == "cancel" and interpretation.has_current_plan:
        from app.services.conversation_state_service import get_conversation_state_service

        await get_conversation_state_service(settings or get_settings()).update_task_state(
            conversation_id,
            org_id,
            {"current_plan": None, "pending_task": None},
            client=client,
        )
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": format_operator_message("pending_plan_cancelled"),
            "voice_section": interpretation.voice_section or voice_system_prompt_section(),
            "task_state": await get_conversation_state_service(
                settings or get_settings()
            ).get_task_state(conversation_id, org_id, client=client),
            "pending_plan_intent": "cancel",
        }

    if interpretation.pending_plan_intent == "modify" and interpretation.has_current_plan:
        from app.services.conversation_state_service import get_conversation_state_service

        # Clear advisory plan so the new instruction can stage a real write/action.
        plan_goal = ""
        current = interpretation.task_state.get("current_plan")
        if isinstance(current, dict):
            plan_goal = str(current.get("goal") or "")
        await get_conversation_state_service(settings or get_settings()).update_task_state(
            conversation_id,
            org_id,
            {"current_plan": None},
            client=client,
        )
        # Rewrite message to carry modify intent + original goal for downstream planning.
        rewrite = interpretation.message
        if plan_goal:
            rewrite = f"{interpretation.message} (regarding plan: {plan_goal})"
        interpretation = TurnInterpretation(
            message=rewrite,
            task_state=await get_conversation_state_service(
                settings or get_settings()
            ).get_task_state(conversation_id, org_id, client=client),
            ledger=interpretation.ledger,
            awaiting_params=interpretation.awaiting_params,
            pending_confirm=False,
            has_current_plan=False,
            pending_plan_intent="modify",
            structured_plan=structured_plan,
            source=source,
            voice_section=interpretation.voice_section or voice_system_prompt_section(),
        )

    connector = get_chat_connector_execution_service(settings)
    turn = await connector.process_turn(
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        message=interpretation.message,
        classification=classification,
        task_state=interpretation.task_state,
        connected_integrations=connected_integrations,
        client=client,
        environment_name=environment_name,
        structured_plan=structured_plan,
    )
    if turn:
        turn = {
            **turn,
            "voice_section": interpretation.voice_section or voice_system_prompt_section(),
        }
        if interpretation.pending_plan_intent:
            turn = {**turn, "pending_plan_intent": interpretation.pending_plan_intent}
    return turn


def bind_canvas_step_args(
    *,
    invoke_action: str,
    step_config: dict[str, Any] | None,
    task_state: dict[str, Any] | None,
    intent_text: str | None = None,
) -> dict[str, Any]:
    """Canvas NL→args: bind ledger + schema heuristics into step config params."""
    from app.services.parameter_ledger import bind_args_from_ledger
    from app.services.schema_param_extractor import extract_action_args_heuristic

    cfg = dict(step_config or {})
    existing = dict(cfg.get("params") or cfg.get("args") or {})
    ledger = get_ledger(task_state)
    text = intent_text or str(cfg.get("intent_text") or cfg.get("prompt") or "")
    if text:
        extracted = extract_action_args_heuristic(
            invoke_action,
            text,
            ledger=ledger,
            existing_args=existing,
        )
        existing = {**existing, **extracted}
    else:
        existing = bind_args_from_ledger(invoke_action, existing, ledger)
    if "params" in cfg or "args" not in cfg:
        cfg["params"] = existing
    else:
        cfg["args"] = existing
    return cfg
