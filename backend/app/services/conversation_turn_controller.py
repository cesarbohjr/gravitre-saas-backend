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
from app.services.gravitree_voice import (
    bind_voice_expression_state,
    format_operator_message,
    reset_voice_expression_state,
    voice_expression_state_snapshot,
    voice_system_prompt_section,
)
from app.services.voice_expression_range import VOICE_EXPRESSION_STATE_KEY
from app.services.parameter_ledger import (
    ParameterLedger,
    get_ledger,
    ingest_message_slots,
    is_awaiting_params,
    ledger_patch,
)
from app.services.pending_reply_classifier import (
    PendingReplyIntent,
    build_pending_snapshot,
    classify_pending_reply,
    emit_pending_reply_audit,
    format_ambiguous_clarify,
    format_pending_meta_answer,
    format_unrelated_hold_prompt,
    has_pending_family,
    map_legacy_plan_intent,
)

logger = get_logger(__name__)

PendingPlanIntent = Literal["continue", "modify", "cancel", "unclear"]
AwaitingParamsIntent = Literal["slot_answer", "meta_clarify", "unrelated"]


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
    awaiting_params_intent: AwaitingParamsIntent | None = None
    pending_reply_intent: PendingReplyIntent | None = None
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

    # Structural Module B — one 7-way classifier for every pending family.
    reply_intent: PendingReplyIntent | None = None
    pending_intent: PendingPlanIntent | None = None
    params_intent: AwaitingParamsIntent | None = None
    if has_pending_family(state):
        reply_intent = await classify_pending_reply(
            text,
            task_state=state,
            settings=settings,
            org_id=org_id,
            use_model=True,
        )
        state = {
            **state,
            "last_pending_reply_intent": reply_intent,
        }
        pending_intent = map_legacy_plan_intent(reply_intent)  # type: ignore[assignment]
        if reply_intent in {"slot_answer", "meta_clarify", "unrelated"}:
            params_intent = reply_intent  # type: ignore[assignment]
        # Do not silently archive sticky plans on unclear — unrelated/ambiguous
        # handlers ask explicitly (hold vs abandon).

    return TurnInterpretation(
        message=text,
        task_state=state,
        ledger=ledger,
        awaiting_params=is_awaiting_params(state),
        pending_confirm=pending_status
        in {"awaiting_confirm", "awaiting_plan_confirm", "awaiting_admin_approval"},
        has_current_plan=bool(current_plan),
        pending_plan_intent=pending_intent,
        awaiting_params_intent=params_intent,
        pending_reply_intent=reply_intent,
        structured_plan=structured_plan,
        source=source,
        voice_section=voice_section,
        metadata={"pending_reply_intent": reply_intent} if reply_intent else {},
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

    from app.services.conversation_state_service import get_conversation_state_service

    state_svc = get_conversation_state_service(settings or get_settings())
    snap = build_pending_snapshot(interpretation.task_state)
    intent = interpretation.pending_reply_intent
    if intent:
        emit_pending_reply_audit(
            client=client,
            org_id=org_id,
            actor_id=user_id,
            conversation_id=conversation_id,
            intent=intent,
            snap=snap,
        )

    # Shared dispatch — meta / unrelated / ambiguous / reject-with-plan before connector traps.
    if intent == "meta_clarify" and has_pending_family(interpretation.task_state):
        return {
            "stop_pipeline": True,
            "dialogue_mode": "clarifying",
            "message": format_pending_meta_answer(snap),
            "voice_section": interpretation.voice_section or voice_system_prompt_section(),
            "task_state": interpretation.task_state,
            "pending_task": (interpretation.task_state or {}).get("pending_task"),
            "pending_reply_intent": intent,
            "workflow_status": "needs clarification",
        }

    if intent == "unrelated" and has_pending_family(interpretation.task_state):
        patch = {
            "pending_hold_prompt": True,
            "pending_hold_new_request": interpretation.message,
            "last_pending_reply_intent": intent,
        }
        await state_svc.update_task_state(
            conversation_id, org_id, patch, client=client
        )
        refreshed = await state_svc.get_task_state(
            conversation_id, org_id, client=client
        )
        hold = format_unrelated_hold_prompt(
            snap, new_request=interpretation.message
        )
        # Social aside while something is pending: warm ack + sober hold (still via
        # pending-reply unrelated — does not bypass the classifier).
        message_out = hold
        try:
            from app.services.conversational_reply_service import (
                compose_pending_social_aside,
            )

            composed = await compose_pending_social_aside(
                interpretation.message,
                task_state=refreshed,
                sober_fallback=hold,
                settings=settings,
                org_id=org_id,
            )
            if composed:
                message_out = composed
        except Exception:  # noqa: BLE001
            message_out = hold
        return {
            "stop_pipeline": True,
            "dialogue_mode": "clarifying",
            "message": message_out,
            "voice_section": interpretation.voice_section or voice_system_prompt_section(),
            "task_state": refreshed,
            "pending_task": refreshed.get("pending_task"),
            "pending_reply_intent": intent,
        }

    if intent == "ambiguous" and has_pending_family(interpretation.task_state):
        clarify = format_ambiguous_clarify(snap)
        message_out = clarify
        try:
            from app.services.conversational_reply_service import (
                compose_pending_social_aside,
            )

            composed = await compose_pending_social_aside(
                interpretation.message,
                task_state=interpretation.task_state,
                sober_fallback=clarify,
                settings=settings,
                org_id=org_id,
            )
            if composed:
                message_out = composed
        except Exception:  # noqa: BLE001
            message_out = clarify
        return {
            "stop_pipeline": True,
            "dialogue_mode": "clarifying",
            "message": message_out,
            "voice_section": interpretation.voice_section or voice_system_prompt_section(),
            "task_state": interpretation.task_state,
            "pending_task": (interpretation.task_state or {}).get("pending_task"),
            "pending_reply_intent": intent,
            "block_fabrication": True,
        }

    # Hold-prompt resolution: reject=abandon pending; confirm=hold pending + continue new ask.
    if snap.hold_prompt_active:
        held_request = str(
            (interpretation.task_state or {}).get("pending_hold_new_request") or ""
        ).strip()
        if intent == "reject":
            await state_svc.update_task_state(
                conversation_id,
                org_id,
                {
                    "pending_task": None,
                    "current_plan": None,
                    "pending_hold_prompt": False,
                    "pending_hold_new_request": None,
                    "pending_steps": [],
                    "completed_steps": [],
                },
                client=client,
            )
            refreshed = await state_svc.get_task_state(
                conversation_id, org_id, client=client
            )
            # Fall through with the held new request (or current message).
            interpretation = TurnInterpretation(
                message=held_request or interpretation.message,
                task_state=refreshed,
                ledger=interpretation.ledger,
                awaiting_params=False,
                pending_confirm=False,
                has_current_plan=False,
                pending_plan_intent=None,
                awaiting_params_intent=None,
                pending_reply_intent=intent,
                structured_plan=structured_plan,
                source=source,
                voice_section=interpretation.voice_section or voice_system_prompt_section(),
            )
        elif intent == "confirm":
            # Hold pending aside: clear hold flag only; keep pending_task for later.
            await state_svc.update_task_state(
                conversation_id,
                org_id,
                {
                    "pending_hold_prompt": False,
                    "pending_on_hold": True,
                    "pending_hold_new_request": None,
                },
                client=client,
            )
            # Park pending_task under pending_on_hold_task and clear active pending
            # so the new request can proceed cleanly.
            parked = (interpretation.task_state or {}).get("pending_task")
            parked_plan = (interpretation.task_state or {}).get("current_plan")
            await state_svc.update_task_state(
                conversation_id,
                org_id,
                {
                    "pending_on_hold_task": parked,
                    "pending_on_hold_plan": parked_plan,
                    "pending_task": None,
                    "current_plan": None,
                    "pending_hold_prompt": False,
                    "pending_on_hold": True,
                },
                client=client,
            )
            refreshed = await state_svc.get_task_state(
                conversation_id, org_id, client=client
            )
            interpretation = TurnInterpretation(
                message=held_request or interpretation.message,
                task_state=refreshed,
                ledger=interpretation.ledger,
                awaiting_params=False,
                pending_confirm=False,
                has_current_plan=False,
                pending_plan_intent=None,
                awaiting_params_intent=None,
                pending_reply_intent=intent,
                structured_plan=structured_plan,
                source=source,
                voice_section=interpretation.voice_section or voice_system_prompt_section(),
            )

    if intent == "reject" and (
        interpretation.has_current_plan
        or interpretation.awaiting_params
        or interpretation.pending_confirm
        or has_pending_family(interpretation.task_state)
    ):
        await state_svc.update_task_state(
            conversation_id,
            org_id,
            {
                "current_plan": None,
                "pending_task": None,
                "pending_hold_prompt": False,
                "pending_steps": [],
                "completed_steps": [],
            },
            client=client,
        )
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": format_operator_message("pending_plan_cancelled"),
            "voice_section": interpretation.voice_section or voice_system_prompt_section(),
            "task_state": await state_svc.get_task_state(
                conversation_id, org_id, client=client
            ),
            "pending_plan_intent": "cancel",
            "pending_reply_intent": "reject",
        }

    if intent == "modify" and (
        interpretation.has_current_plan or has_pending_family(interpretation.task_state)
    ):
        plan_goal = ""
        current = interpretation.task_state.get("current_plan")
        if isinstance(current, dict):
            plan_goal = str(current.get("goal") or "")
        # Clear advisory plan / confirm traps so modify can re-stage; keep awaiting_params
        # args so slot patches can bind on resume.
        clear_patch: dict[str, Any] = {"current_plan": None, "pending_hold_prompt": False}
        pending = interpretation.task_state.get("pending_task")
        if isinstance(pending, dict) and str(pending.get("status") or "") in {
            "awaiting_confirm",
            "awaiting_plan_confirm",
            "awaiting_admin_approval",
            "awaiting_step_confirm",
        }:
            clear_patch["pending_task"] = None
        await state_svc.update_task_state(
            conversation_id, org_id, clear_patch, client=client
        )
        rewrite = interpretation.message
        if plan_goal:
            rewrite = f"{interpretation.message} (regarding plan: {plan_goal})"
        interpretation = TurnInterpretation(
            message=rewrite,
            task_state=await state_svc.get_task_state(
                conversation_id, org_id, client=client
            ),
            ledger=interpretation.ledger,
            awaiting_params=is_awaiting_params(
                await state_svc.get_task_state(conversation_id, org_id, client=client)
            ),
            pending_confirm=False,
            has_current_plan=False,
            pending_plan_intent="modify",
            awaiting_params_intent=interpretation.awaiting_params_intent,
            pending_reply_intent="modify",
            structured_plan=structured_plan,
            source=source,
            voice_section=interpretation.voice_section or voice_system_prompt_section(),
        )

    connector = get_chat_connector_execution_service(settings)
    # Module D expression range — reuse parent bind from agent_intelligence when present.
    voice_token = bind_voice_expression_state(
        interpretation.task_state,
        reuse_if_bound=True,
        conversation_id=conversation_id,
        org_id=org_id,
        client=client,
        settings=settings,
    )
    try:
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
            pending_reply_intent=interpretation.pending_reply_intent,
        )
        voice_snap = voice_expression_state_snapshot()
        if voice_snap and conversation_id and org_id and voice_token is not None:
            try:
                await get_conversation_state_service(settings or get_settings()).update_task_state(
                    conversation_id,
                    org_id,
                    {VOICE_EXPRESSION_STATE_KEY: voice_snap},
                    client=client,
                )
            except Exception:  # noqa: BLE001
                logger.debug(
                    "voice_expression_last persist skipped conversation_id=%s",
                    conversation_id,
                    exc_info=True,
                )
    finally:
        reset_voice_expression_state(voice_token)
    if turn:
        turn = {
            **turn,
            "voice_section": interpretation.voice_section or voice_system_prompt_section(),
        }
        if interpretation.pending_plan_intent:
            turn = {**turn, "pending_plan_intent": interpretation.pending_plan_intent}
        if interpretation.pending_reply_intent:
            turn = {**turn, "pending_reply_intent": interpretation.pending_reply_intent}
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
