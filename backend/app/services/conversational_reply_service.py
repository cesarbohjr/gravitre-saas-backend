"""First-class conversational reply path (no connector mapping / write gate).

Uses Module D voice banks via ``voice_expression_range`` for priority categories
(greeting / small_talk / thanks / banter / venting / meta). Selection is
deterministic rotation on ``task_state.voice_expression_last`` — same mechanism
as connector/status phrase variety. Does not change turn-gate classification.
"""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.conversational_turn_gate import ConversationalGateDecision
from app.services.gravitre_voice import (
    format_operator_message,
    humor_permitted,
)
from app.services.voice_expression_range import pick_expression

logger = get_logger(__name__)

# Priority categories — bank-first (known identical-fallback gap).
_BANK_KEYS: dict[str, str] = {
    "greeting": "conversational.greeting",
    "small_talk": "conversational.small_talk",
    "thanks": "conversational.thanks",
    "banter": "conversational.banter",
    "venting": "conversational.venting",
    "meta_capability": "conversational.meta_capability",
}


def _recent_context_lines(task_state: dict[str, Any] | None, history: list[dict[str, Any]] | None) -> str:
    bits: list[str] = []
    state = task_state if isinstance(task_state, dict) else {}
    recent = list(state.get("recent_user_messages") or [])[-4:]
    for item in recent:
        text = str(item or "").strip()
        if text:
            bits.append(f"user: {text[:160]}")
    for row in (history or [])[-6:]:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "")
        content = str(row.get("content") or row.get("text") or "").strip()
        if role in {"user", "assistant"} and content:
            bits.append(f"{role}: {content[:180]}")
    return "\n".join(bits[-8:])


def build_capability_snapshot(
    *,
    connected_integrations: list[str] | None,
    client: Any = None,
    org_id: str | None = None,
) -> str:
    """Live-ish inventory for meta questions — Connected connectors + approval model."""
    connected = [str(c).strip() for c in (connected_integrations or []) if str(c).strip()]
    if not connected and client is not None and org_id:
        try:
            from app.services.tool_registry import ToolRegistry

            connected = ToolRegistry.list_connected_integrations(client, org_id)
        except Exception:  # noqa: BLE001
            connected = []
    if connected:
        labels = ", ".join(sorted({c.replace("_", " ").title() for c in connected}))
        connectors_line = f"Connected for this org right now: {labels}."
    else:
        connectors_line = (
            "No connectors are Connected for this organization yet — "
            "set them up at /connectors when you want vendor actions."
        )
    return (
        f"{connectors_line} "
        "Writes go through catalog write-authority with explicit approval when required "
        "(Decision Queue / reply **yes**). I can also help with multi-step plans, "
        "run history, and marketplace intelligence packs once connectors are Connected."
    )


def phrase_for_conversational_category(
    category: str,
    *,
    capability: str = "",
) -> str:
    """Deterministic Module D phrase for a conversational category (bound state rotates)."""
    cat = (category or "small_talk").strip().lower()
    if cat == "other":
        cat = "small_talk"
    key = _BANK_KEYS.get(cat, "conversational.small_talk")
    ctx: dict[str, Any] = {}
    if key == "conversational.meta_capability":
        ctx["capability"] = (
            capability
            or "Connected tools, write-authority with approval when required, plans, and packs."
        )
    text = pick_expression(key, ctx=ctx)
    if text:
        return text
    # Unbound / missing bank — stable house defaults (index 0 equivalents).
    defaults = {
        "conversational.greeting": "Hey — here when you need a connector run, a plan, or a quick check.",
        "conversational.small_talk": (
            "Doing well — here when you need a connector run, a plan, or a quick check."
        ),
        "conversational.thanks": "You're welcome. Ready when you are.",
        "conversational.banter": "Ha — noted. What should we tackle next?",
        "conversational.venting": (
            "That's a rough spot. Tell me the one check you want first and we'll start there."
        ),
        "conversational.meta_capability": (
            f"I am Gravitre — a calm operator for your Connected tools. {ctx.get('capability', '')}"
        ).strip(),
    }
    return defaults.get(key, defaults["conversational.small_talk"])


async def generate_conversational_reply(
    message: str,
    *,
    decision: ConversationalGateDecision,
    settings: Settings | None = None,
    org_id: str | None = None,
    task_state: dict[str, Any] | None = None,
    conversation_history: list[dict[str, Any]] | None = None,
    connected_integrations: list[str] | None = None,
    client: Any = None,
    allow_humor: bool = False,
    pending_sober_note: str | None = None,
) -> str:
    """Generate a Module D-voiced conversational reply (no tools / no outcomes).

    Priority categories use expression banks (deterministic rotation). Model path
    is reserved for rare ``other`` turns with rich context — never replaces the
    bank for greeting/small_talk/thanks/banter/venting/meta.
    """
    _ = settings or get_settings()
    _ = message
    _ = conversation_history
    category = decision.category or "other"
    humor_ok = humor_permitted(kind="success_win", allow_humor=allow_humor) and category in {
        "banter",
        "greeting",
        "small_talk",
        "thanks",
    }
    if pending_sober_note:
        humor_ok = False
    _ = humor_ok  # banks already encode rare dry banter; flag reserved for future model path

    capability = ""
    if category == "meta_capability" or re_search_meta(message):
        capability = build_capability_snapshot(
            connected_integrations=connected_integrations,
            client=client,
            org_id=org_id,
        )
        if category != "meta_capability":
            category = "meta_capability"

    # Ensure rotation sees conversation-scoped last indices when caller bound state.
    # If unbound (unit tests), pick_expression returns index 0 — stable.
    body = phrase_for_conversational_category(category, capability=capability)
    if pending_sober_note:
        return f"{body.rstrip()}\n\n{pending_sober_note}"
    return body


# Meta / capability questions — answer from agent config only; never retrieve.
# Prefer full-message match so "what can you help with our SEO campaign" stays task-shaped.
_META_CAPABILITY_FULL = (
    r"(?i)^\s*("
    r"what can you do"
    r"|what can you help(?:\s+me|\s+us)?(?:\s+with)?"
    r"|what (can|do) you help (me|us)?\s*(with)?"
    r"|how can you help(?:\s+me|\s+us)?"
    r"|what are you able to do"
    r"|what tools? do you (have|have access to|support|offer)"
    r"|what('?s| is) your (capability|capabilities|skillset|skills)"
    r"|are you (an )?(human or )?ai"
    r"|who are you"
    r"|what are you"
    r"|human or ai"
    r")\s*\??\s*$"
)


def re_search_meta(message: str) -> bool:
    """True for meta/capability asks (UI suggested-prompt class + variants)."""
    import re

    text = (message or "").strip()
    if not text:
        return False
    return bool(re.match(_META_CAPABILITY_FULL, text))


async def generate_social_ack(
    social_portion: str,
    *,
    org_id: str | None = None,
    settings: Settings | None = None,
) -> str:
    """One short warm line for mixed turns (task continues separately)."""
    _ = org_id
    _ = settings
    text = (social_portion or "").strip().lower()
    if any(x in text for x in ("haha", "lol", "lmao", "funny", "nice one", "nice")):
        return pick_expression("conversational.mixed_ack_banter") or "Ha — noted."
    if "thank" in text or text in {"ty", "thx"}:
        return pick_expression("conversational.mixed_ack_thanks") or "You're welcome."
    if any(x in text for x in ("hey", "hi", "hello", "good morning", "good afternoon")):
        return pick_expression("conversational.mixed_ack_greeting") or "Hey — on it."
    # Default short warm beat
    return pick_expression("conversational.mixed_ack_greeting") or "On it."


async def compose_pending_social_aside(
    message: str,
    *,
    task_state: dict[str, Any] | None,
    sober_fallback: str,
    settings: Settings | None = None,
    org_id: str | None = None,
) -> str | None:
    """Warm social beat + sober pending note. None when the message is task-shaped.

    Does not bypass the pending-reply classifier — callers invoke this only after
    the classifier already chose unrelated/ambiguous. Pure task-shaped asides
    keep the classifier's abandon/hold or clarify copy unchanged.
    """
    from app.services.conversational_turn_gate import heuristic_turn_shape

    social = heuristic_turn_shape(message)
    if not social or social.shape != "conversational":
        return None
    sober = sober_pending_approval_note(task_state) or (sober_fallback or "").strip()
    if not sober:
        return None
    return await generate_conversational_reply(
        message,
        decision=social,
        settings=settings,
        org_id=org_id,
        task_state=task_state,
        allow_humor=social.category in {"banter", "greeting", "thanks"},
        pending_sober_note=sober,
    )


def sober_pending_approval_note(task_state: dict[str, Any] | None) -> str | None:
    """Sober one-liner when approval is pending — never humorous."""
    state = task_state if isinstance(task_state, dict) else {}
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}
    status = str(pending.get("status") or "")
    if status not in {
        "awaiting_confirm",
        "awaiting_admin_approval",
        "awaiting_plan_confirm",
        "awaiting_step_confirm",
    }:
        return None
    params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
    label = str(
        params.get("label")
        or pending.get("label")
        or params.get("invoke_action")
        or "the pending write"
    ).strip()
    return format_operator_message(
        "approval_needed_requester",
        label=label,
    ) + " Reply **yes** to approve, or **cancel** to drop it."
