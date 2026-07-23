"""Module B pending-reply ownership on the unified LIVE path (Phase 4).

Unified turn must not bypass classify_pending_reply / formatted hold prompts.
"""
from __future__ import annotations

import re
from typing import Any

from app.config import Settings, get_settings
from app.services.conversational_reply_service import compose_pending_social_aside
from app.services.pending_reply_classifier import (
    PendingReplyIntent,
    build_pending_snapshot,
    classify_pending_reply,
    emit_pending_reply_audit,
    format_ambiguous_clarify,
    format_pending_meta_answer,
    format_unrelated_hold_prompt,
    has_pending_family,
)

_HOLD_ABANDON_RE = re.compile(
    r"\babandon\b.*\bhold\b|\bhold\b.*\babandon\b|reply [`'\"]?abandon[`'\"]? or [`'\"]?hold",
    re.I,
)


async def resolve_unified_live_pending_reply(
    *,
    message: str,
    task_state: dict[str, Any] | None,
    org_id: str,
    user_id: str,
    conversation_id: str | None,
    client: Any,
    settings: Settings | None = None,
) -> "UnifiedTurnShadowResult | None":
    """Return a deterministic LIVE result when Module B owns this pending turn."""
    from app.services.unified_turn_reasoning_service import UnifiedTurnShadowResult

    if not has_pending_family(task_state):
        return None

    active = settings or get_settings()
    snap = build_pending_snapshot(task_state)
    intent: PendingReplyIntent = await classify_pending_reply(
        message,
        task_state=task_state,
        settings=active,
        org_id=org_id,
        use_model=True,
    )
    emit_pending_reply_audit(
        client=client,
        org_id=org_id,
        actor_id=user_id,
        conversation_id=conversation_id or "",
        intent=intent,
        snap=snap,
    )

    if intent in {"confirm", "reject", "modify", "slot_answer"}:
        return None

    if intent == "unrelated":
        text = format_unrelated_hold_prompt(snap, new_request=message)
        return UnifiedTurnShadowResult(
            outcome_kind="clarifying_question",
            user_message=text,
            live_served=True,
            model="pending_reply_classifier",
        )

    if intent == "meta_clarify":
        text = format_pending_meta_answer(snap)
        return UnifiedTurnShadowResult(
            outcome_kind="clarifying_question",
            user_message=text,
            live_served=True,
            model="pending_reply_classifier",
        )

    if intent == "ambiguous":
        sober = format_ambiguous_clarify(snap)
        aside = await compose_pending_social_aside(
            message,
            task_state=task_state,
            sober_fallback=sober,
            settings=active,
            org_id=org_id,
        )
        text = aside or sober
        return UnifiedTurnShadowResult(
            outcome_kind="clarifying_question",
            user_message=text,
            live_served=True,
            model="pending_reply_classifier",
        )

    return None


async def resolve_unified_live_meta_capability_reply(
    *,
    message: str,
    task_state: dict[str, Any] | None,
    org_id: str,
    connected_integrations: list[str] | None,
    client: Any,
    settings: Settings | None = None,
) -> "UnifiedTurnShadowResult | None":
    """Meta capability questions use the same expression path as classical Module D."""
    from app.services.conversational_reply_service import generate_conversational_reply, re_search_meta
    from app.services.conversational_turn_gate import ConversationalGateDecision
    from app.services.pending_reply_classifier import has_pending_family
    from app.services.unified_turn_reasoning_service import UnifiedTurnShadowResult

    if has_pending_family(task_state):
        return None
    if not re_search_meta(message):
        return None
    if not re.search(r"(?i)what can you do", message or ""):
        return None

    decision = ConversationalGateDecision(
        shape="conversational",
        reason="meta_capability_unified_live",
        category="meta_capability",
    )
    text = await generate_conversational_reply(
        message,
        decision=decision,
        settings=settings or get_settings(),
        org_id=org_id,
        task_state=task_state,
        connected_integrations=list(connected_integrations or []),
        client=client,
    )
    return UnifiedTurnShadowResult(
        outcome_kind="conversational_reply",
        user_message=text,
        live_served=True,
        model="conversational_meta_capability",
    )


def unified_live_message_violates_no_pending_hold(*, message: str, task_state: dict[str, Any] | None) -> bool:
    """True when model invented hold/abandon without real pending state."""
    if has_pending_family(task_state):
        return False
    return bool(_HOLD_ABANDON_RE.search(message or ""))
