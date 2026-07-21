"""First-class conversational reply path (no connector mapping / write gate).

Uses Module D voice + FAST/low generation. Optional light humor only when
``allow_humor`` is true and no governance-sensitive pending is active.
"""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.conversational_turn_gate import ConversationalGateDecision
from app.services.gravitree_voice import (
    apply_voice,
    format_operator_message,
    humor_permitted,
    voice_system_prompt_section,
)

logger = get_logger(__name__)


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
    """Generate a Module D-voiced conversational reply (no tools / no outcomes)."""
    active = settings or get_settings()
    category = decision.category or "other"
    humor_ok = humor_permitted(kind="success_win", allow_humor=allow_humor) and category in {
        "banter",
        "greeting",
        "small_talk",
        "thanks",
    }
    # Governance-sensitive note always stays sober — never wrap it in a joke.
    if pending_sober_note:
        humor_ok = False

    context = _recent_context_lines(task_state, conversation_history)
    capability = ""
    if category == "meta_capability" or re_search_meta(message):
        capability = build_capability_snapshot(
            connected_integrations=connected_integrations,
            client=client,
            org_id=org_id,
        )

    system = apply_voice(
        "You are Gravitre in conversational mode — no tools, no connector actions, "
        "no fabricated business metrics.\n"
        f"{voice_system_prompt_section()}\n"
        "Reply like a sharp, friendly colleague. Short (1–3 sentences). "
        "Warm and specific when context exists; never corporate template language. "
        "Humor is light and rare — most replies are simply warm and clear. "
        "Never invent connector states, run counts, or deal numbers. "
        "If the user vents about a connector, acknowledge the friction and offer a "
        "concrete next check without turning it into a support ticket."
    )
    if humor_ok:
        system += "\nA single light, dry beat of humor is allowed if it fits; never cute."
    else:
        system += "\nNo jokes this turn."

    user_prompt = (
        f"Category: {category}\n"
        f"User: {message.strip()}\n"
        f"Conversation context:\n{context or '(none)'}\n"
    )
    if capability:
        user_prompt += f"\nReal capability inventory (use only this):\n{capability}\n"
    if pending_sober_note:
        user_prompt += (
            "\nAfter the warm reply, append this sober note verbatim on its own paragraph "
            f"(do not joke about it):\n{pending_sober_note}\n"
        )

    try:
        from app.services.model_router import TaskType, get_model_router

        response = await get_model_router(active).complete(
            task_type=TaskType.CLASSIFICATION,  # FAST/low — short social reply
            prompt=user_prompt,
            system_prompt=system,
            temperature=0.4 if humor_ok else 0.2,
            max_tokens=220,
            org_id=org_id,
        )
        text = str(response.content or "").strip()
        if text:
            if pending_sober_note and pending_sober_note not in text:
                text = f"{text.rstrip()}\n\n{pending_sober_note}"
            return text
    except Exception as exc:  # noqa: BLE001
        logger.debug("conversational reply model failed: %s", exc)

    return _fallback_reply(category, message, capability, pending_sober_note)


def re_search_meta(message: str) -> bool:
    import re

    return bool(re.search(r"(?i)what can you do|are you (an )?ai|who are you|what are you", message or ""))


def _fallback_reply(
    category: str,
    message: str,
    capability: str,
    pending_sober_note: str | None,
) -> str:
    if category == "meta_capability" and capability:
        body = f"I am Gravitre — a calm operator for your Connected tools. {capability}"
    elif category == "thanks":
        body = "You're welcome. Ready when you are."
    elif category == "venting":
        body = (
            "That friction is real. When you want to dig in, we can check the connector "
            "at /connectors (Connected / Healthy / Authenticated) and retry the action."
        )
    elif category == "banter":
        body = "Ha — noted. What should we tackle next?"
    else:
        # Prefer a house-style insufficient-info-adjacent warmth without claiming work.
        body = "Doing well — here when you need a connector run, a plan, or a quick check."
    if pending_sober_note:
        return f"{body}\n\n{pending_sober_note}"
    return body


async def generate_social_ack(social_portion: str, *, org_id: str | None = None, settings: Settings | None = None) -> str:
    """One short warm line for mixed turns (task continues separately)."""
    decision = ConversationalGateDecision(
        shape="conversational",
        reason="mixed_social_ack",
        social_portion=social_portion,
        category="banter" if any(x in social_portion.lower() for x in ("haha", "lol", "nice")) else "small_talk",
    )
    reply = await generate_conversational_reply(
        social_portion,
        decision=decision,
        settings=settings,
        org_id=org_id,
        allow_humor=True,
    )
    # Keep ack to one sentence for mixed turns.
    return reply.split("\n")[0].strip()[:280]


def sober_pending_approval_note(task_state: dict[str, Any] | None) -> str | None:
    """Sober one-liner when approval is pending — never humorous."""
    state = task_state if isinstance(task_state, dict) else {}
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}
    status = str(pending.get("status") or "")
    if status not in {"awaiting_confirm", "awaiting_admin_approval", "awaiting_plan_confirm", "awaiting_step_confirm"}:
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
