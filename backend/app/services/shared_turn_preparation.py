"""Turn preparation every conversational surface runs before the brain.

Text chat (``POST /api/assistant/chat``) and voice (Pipecat and the legacy HTTP
duplex path) are entry surfaces into the same ``execute_task_streaming``. Before
this module, only text built the canonical system prompt, applied the
prompt-injection note and ran the model guardrails (kill switch, rate limit,
budget, input moderation, model policy). Voice skipped all of them, so the same
words could be answered under a different persona and without the org's
limits. These helpers are the single implementation both surfaces call; what
stays surface-specific is only how a refusal is presented (an HTTP status for
text, a short spoken sentence for voice).
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# Spoken equivalents of the HTTP errors text chat returns for the same guardrail.
SPOKEN_GUARDRAIL_MESSAGES: dict[str, str] = {
    "disabled": "The assistant is turned off for your workspace right now.",
    "rate_limited": "We've hit the usage limit for the moment. Give it a minute and ask me again.",
    "budget_exceeded": "Your workspace has used its AI budget for this period, so I can't run that right now.",
    "content_flagged": "I can't help with that request.",
    "invalid": "I couldn't process that request. Could you say it another way?",
    "model_policy": "Your workspace policy doesn't allow the model this needs, so I can't run that right now.",
}


class TurnGuardrailBlocked(Exception):
    """A guardrail refused the turn. ``kind`` keys SPOKEN_GUARDRAIL_MESSAGES."""

    def __init__(self, kind: str, detail: str = "") -> None:
        super().__init__(detail or kind)
        self.kind = kind
        self.detail = detail

    @property
    def spoken(self) -> str:
        return SPOKEN_GUARDRAIL_MESSAGES.get(self.kind, SPOKEN_GUARDRAIL_MESSAGES["invalid"])


def apply_department_scope(system_prompt: str, department: str | None, cross_department: bool = False) -> str:
    department = (department or "").strip() or None
    if cross_department:
        return (
            f"{system_prompt}\n\nOperator scope: cross-department cowork. "
            f"Primary department: {department or 'all'}. "
            "Coordinate handoffs across teams. Do not put this scope label into "
            "tool arguments or outbound message bodies."
        )
    if department:
        return (
            f"{system_prompt}\n\nOperator department context: {department}. "
            "Use this for prioritization and handoffs only — never copy this label "
            "into tool arguments or outbound message bodies."
        )
    return system_prompt


def build_turn_system_prompt(
    settings: Any,
    org_id: str,
    *,
    user_id: str | None,
    agent_id: str | None,
    query: str | None,
    environment_name: str = "production",
    department: str | None = None,
    cross_department: bool = False,
) -> str:
    """The canonical assistant system prompt (persona, org context, agent memory, department)."""
    from app.routers.assistant import _build_assistant_system_prompt

    prompt = _build_assistant_system_prompt(
        settings,
        org_id,
        user_id=user_id,
        agent_id=agent_id,
        query=query,
        environment_name=environment_name,
    )
    return apply_department_scope(prompt, department, cross_department)


async def harden_against_injection(
    settings: Any,
    *,
    org_id: str,
    conversation_id: str | None,
    system_prompt: str,
    user_text: str,
    surface: str,
) -> str:
    """Append the injection-hardening note and audit it when the user text looks like an injection."""
    if not getattr(settings, "prompt_injection_detection_enabled", True):
        return system_prompt
    from app.services.ai_guardrails import detect_prompt_injection, injection_hardening_note

    detected, reason = detect_prompt_injection(user_text)
    if not detected:
        return system_prompt
    from app.routers.assistant import _log_assistant_guardrail_event

    await _log_assistant_guardrail_event(
        settings,
        org_id,
        "prompt_injection.detected",
        {"reason": reason, "conversation_id": conversation_id, "surface": surface},
    )
    return f"{system_prompt}\n\n{injection_hardening_note(reason)}"


async def enforce_turn_guardrails(
    settings: Any,
    *,
    org_id: str,
    user_text: str,
    system_prompt: str,
    history: list[dict[str, Any]] | None,
    task_type: Any,
    model_override: str | None,
    light: bool = False,
    router: Any = None,
) -> None:
    """Kill switch, rate limit, budget, then (unless ``light``) moderation and model policy.

    Raises the provider guardrail errors unchanged so each surface maps them to
    its own presentation. ``light`` is the deterministic computer-use READ path
    that text already exempts from network moderation.
    """
    from app.services.ai_guardrails import AIServiceDisabledError, enforce_budget, enforce_rate_limit
    from app.services.model_router import get_model_router

    if light:
        if getattr(settings, "disable_ai", False):
            raise AIServiceDisabledError()
        enforce_rate_limit(org_id, settings)
        enforce_budget(org_id, settings)
        return
    await (router or get_model_router()).prepare_stream(
        task_type=task_type,
        prompt=user_text,
        system_prompt=system_prompt,
        context=history or [],
        org_id=org_id,
        model_override=model_override,
    )


def classify_guardrail_error(exc: BaseException) -> str | None:
    """Map a guardrail error to a SPOKEN_GUARDRAIL_MESSAGES key, or None when it is not one."""
    from app.services.ai_guardrails import (
        AIBudgetExceededError,
        AIContentFlaggedError,
        AIModelPolicyError,
        AIRateLimitError,
        AIServiceDisabledError,
    )
    from app.services.providers.base import ProviderInvalidResponseError

    if isinstance(exc, AIServiceDisabledError):
        return "disabled"
    if isinstance(exc, AIRateLimitError):
        return "rate_limited"
    if isinstance(exc, AIBudgetExceededError):
        return "budget_exceeded"
    if isinstance(exc, AIContentFlaggedError):
        return "content_flagged"
    if isinstance(exc, AIModelPolicyError):
        return "model_policy"
    if isinstance(exc, ProviderInvalidResponseError):
        return "invalid"
    return None


async def guard_spoken_turn(
    settings: Any,
    *,
    org_id: str,
    user_text: str,
    system_prompt: str,
    history: list[dict[str, Any]] | None,
    mode: str | None,
) -> None:
    """Voice entry: the same guardrails text runs, raising TurnGuardrailBlocked on refusal."""
    from app.services.assistant_mode import resolve_assistant_model

    model_override, task_type = resolve_assistant_model(mode, None)
    try:
        await enforce_turn_guardrails(
            settings,
            org_id=org_id,
            user_text=user_text,
            # Moderation screens what the caller said. Sending Gravitre's own
            # multi-thousand-token system prompt along with it made the gate
            # in front of the first spoken word several times slower on every
            # voice turn and checked nothing the user wrote. The system prompt
            # still drives the brain unchanged.
            system_prompt="",
            history=history,
            task_type=task_type,
            model_override=model_override,
        )
    except Exception as exc:  # noqa: BLE001
        kind = classify_guardrail_error(exc)
        if kind is None:
            raise
        raise TurnGuardrailBlocked(kind, str(exc)) from exc


def persist_turn_summary(
    settings: Any,
    *,
    conversation_id: str | None,
    org_id: str,
    user_id: str | None,
    complete: Any,
) -> None:
    """Save the rolling summary the brain produced, exactly as text chat does."""
    if (
        complete is None
        or not getattr(complete, "summary_updated", False)
        or not conversation_id
        or not user_id
        or not getattr(complete, "summary", None)
    ):
        return
    from app.services.conversation_context_service import persist_conversation_summary
    from app.workflows.repository import get_supabase_client

    persist_conversation_summary(
        get_supabase_client(settings),
        conversation_id=conversation_id,
        org_id=org_id,
        user_id=user_id,
        summary=complete.summary,
    )


def persist_completed_turn(
    settings: Any,
    *,
    org_id: str,
    user_id: str,
    conversation_id: str | None,
    user_text: str,
    assistant_text: str,
    complete: Any,
) -> tuple[str | None, str | None]:
    """Save a finished turn to the same durable conversation store text chat uses.

    Appends the user and assistant messages (creating the conversation when
    there is none yet) and records the completed turn in memory. Returns
    ``(conversation_id, assistant_message_id)``; ``(None, None)`` when nothing
    was saved. Blocking: call it from a worker thread in async code.
    """
    if not assistant_text.strip():
        return None, None
    from app.routers.assistant import _persist_conversation_turn, _remember_completed_turn

    tool_results = list(getattr(complete, "tool_results", None) or [])
    persisted_id, assistant_id = _persist_conversation_turn(
        settings,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        user_text=user_text,
        assistant_text=assistant_text,
        tool_results=tool_results,
        assistant_message_id=str(getattr(complete, "message_id", None) or "") or None,
    )
    if persisted_id:
        _remember_completed_turn(
            settings=settings,
            org_id=org_id,
            conversation_id=persisted_id,
            user_text=user_text,
            assistant_text=assistant_text,
            tool_results=tool_results,
            assistant_message_id=assistant_id,
        )
    return persisted_id, assistant_id


async def prepare_turn_conversation(
    settings: Any,
    *,
    org_id: str,
    user_id: str | None,
    conversation_id: str | None,
    user_text: str,
    ensure_row: bool = True,
) -> str | None:
    """Conversation row and parameter ledger before the brain runs, as text chat does.

    STA-306: the row must exist before the ReAct write gate persists a
    pending_task mid-stream, otherwise the approval is a silent no-op and the
    next "yes" has nothing to confirm. Module B: names, emails and dates the
    user mentions are written to the conversation ledger before the turn, so
    an early return in the brain cannot drop them. Never raises.
    """
    if not conversation_id or not user_id or not org_id:
        return conversation_id
    from app.services.conversation_state_service import get_conversation_state_service

    state_svc = get_conversation_state_service(settings)
    if ensure_row:
        try:
            conversation_id = await state_svc.ensure_owned_conversation(
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                title=(user_text or "New conversation")[:80],
            )
        except Exception as exc:  # noqa: BLE001 - never make a turn unavailable
            logger.warning("turn_conversation_ensure_failed conversation_id=%s error=%s", conversation_id, exc)
            return conversation_id
    text = (user_text or "").strip()
    if not conversation_id or not text:
        return conversation_id
    try:
        from app.services.parameter_ledger import get_ledger, ingest_message_slots, ledger_patch

        prior = await state_svc.get_task_state(conversation_id, org_id)
        ledger = ingest_message_slots(
            text,
            turn_index=len(list((prior or {}).get("recent_user_messages") or [])) + 1,
            ledger=get_ledger(prior),
        )
        await state_svc.update_task_state(
            conversation_id,
            org_id,
            {**ledger_patch(ledger), "recent_user_messages": [text]},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("turn_ledger_ingest_failed conversation_id=%s error=%s", conversation_id, exc)
    return conversation_id
