"""Shared operator-task detector for canned-reply fail-open.

Keyword shortcuts (IA FAQ, ambiguous-open clarify, venting, response cache,
spoken lite-path) must never replace reasoning for a real connector/setup
request. One production instance already did: Settings FAQ substring matching
on a Google Ads campaign brief.

High-confidence social/FAQ matchers stay; anything that looks like a real
operator task falls through to CognitiveTurnKernel / unified LIVE.
"""

from __future__ import annotations

import re
from typing import Any

# Phrases that mean "this is a real job," not a one-line FAQ or vent.
OPERATOR_TASK_HINTS: tuple[str, ...] = (
    "google ads",
    "googleads",
    "adwords",
    "don't execute",
    "do not execute",
    "without my approval",
    "once i approve",
    "set it up in",
    "create four campaigns",
    "create 4 campaigns",
    "campaign strategy",
    "campaign-by-campaign",
    "ad groups",
    "negative keywords",
    "check that my",
    "actually connected",
    "right access",
)

_OPERATOR_TASK_RE = re.compile(
    r"(?i)\b("
    r"google\s*ads|adwords|ad\s*groups?|negative\s+keywords?|"
    r"campaign\s+strategy|create\s+(?:four|4|\d+)\s+campaigns|"
    r"don'?t\s+execute|do\s+not\s+execute|without\s+my\s+approval|"
    r"once\s+i\s+approve|set\s+it\s+up\s+in"
    r")\b"
)

# Concrete multi-step work even without the Google Ads lexicon.
# Do not treat "ugh this HubSpot connector is annoying" as a task (Rule 10).
_OPERATOR_WORK_RE = re.compile(
    r"(?i)\b("
    r"create\s+(?:an?\s+|the\s+)?(?:\w+\s+){0,3}(?:campaigns?|ad\s*groups?|lists?)|"
    r"check\s+(?:that\s+)?my\s+.+\s+account|"
    r"is\s+(?:my\s+|our\s+)?(?:hubspot|apollo|salesforce|gmail|google\s*ads|slack)"
    r"\s+(?:account\s+)?connected|"
    r"approval\s+first|show\s+me\s+the\s+(?:complete\s+)?plan|"
    r"don'?t\s+execute|without\s+my\s+approval"
    r")\b"
)


def looks_like_operator_task(message: str) -> bool:
    """True when a canned shortcut must fall through to real reasoning/tools."""
    text = (message or "").strip()
    if not text:
        return False
    try:
        from app.services.connector_status_reply_service import parse_connector_status_question

        parsed = parse_connector_status_question(text)
        if parsed is not None and parsed.kind.value == "connection":
            from app.services.connector_status_reply_service import (
                _CHECK_WHETHER_CONNECTED_RE,
                _IS_VENDOR_CONNECTED_RE,
                _STATUS_OF_VENDOR_RE,
            )

            # Only whole-utterance status asks skip the operator-task path.
            # Substring "is … connected" inside a job brief must still reason.
            if (
                _IS_VENDOR_CONNECTED_RE.match(text)
                or _CHECK_WHETHER_CONNECTED_RE.match(text)
                or _STATUS_OF_VENDOR_RE.match(text)
            ):
                extra_job = re.search(
                    r"(?i)\b(and what|access does|create |campaign|set it up)\b",
                    text,
                )
                if extra_job is None:
                    return False
    except Exception:  # noqa: BLE001
        pass
    lowered = text.lower()
    if any(hint in lowered for hint in OPERATOR_TASK_HINTS):
        return True
    if _OPERATOR_TASK_RE.search(text) or _OPERATOR_WORK_RE.search(text):
        return True
    return False


def should_keep_full_reasoning_for_spoken(message: str) -> bool:
    """Spoken lite-path (fast + conversational depth) is for chitchat, not jobs."""
    if looks_like_operator_task(message):
        return True
    try:
        from app.services.chat_action_mapper import GOOGLE_ADS_STRUCTURE_INTENT

        if GOOGLE_ADS_STRUCTURE_INTENT.search(message or ""):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.services.conversational_planning_engine import is_direct_connector_write_intent

        if is_direct_connector_write_intent(message or ""):
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def is_operator_task_shaped(message: str) -> bool:
    """Single shared definition: this turn is ineligible for every canned shortcut.

    Reuses the proven detectors (operator-task lexicon, Google Ads structure,
    direct connector writes). The Intent Gateway is the only caller that may
    treat this as a hard ineligibility gate.
    """
    if looks_like_operator_task(message):
        return True
    if should_keep_full_reasoning_for_spoken(message):
        return True
    try:
        from app.services.conversational_planning_engine import is_direct_connector_write_intent

        if is_direct_connector_write_intent(message or ""):
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def use_spoken_lite_path(
    *,
    spoken_mode: bool,
    routing_tier: str,
    message: str,
    history: list[dict[str, Any]] | None = None,
    task_state: dict[str, Any] | None = None,
) -> bool:
    """Skip understand / classify / enrich only for light spoken turns.

    Light comes from the shared tier classifier, which already disqualifies
    business nouns, task verbs, operator tasks and continuations of a deep
    exchange. Any pending approval, offered action or active plan in
    ``task_state`` keeps the full pipeline, as does any routing escalation.
    Moderation, rate limit and the kill switch run on the voice entry
    surfaces before this point and are not affected.
    """
    if not spoken_mode or not (message or "").strip():
        return False
    if (routing_tier or "").lower() not in {"simple", "fast", "low"}:
        return False
    from app.services.conversation_tier import (
        classify_conversation_tier,
        has_pending_task_state,
    )

    if has_pending_task_state(task_state):
        return False
    return classify_conversation_tier(message, history=history, task_state=task_state).tier == "light"


def should_skip_unified_live_guards(
    *,
    spoken_mode: bool,
    reasoning_depth: str,
    has_pending: bool,
    message: str,
) -> bool:
    """Absorbed by the Intent Gateway. Kernel fallthrough always keeps LIVE guards."""
    return False


def should_force_live_connector_pipeline(message: str) -> bool:
    """LIVE must not answer real jobs in spoken prose; use orch/classical instead."""
    return looks_like_operator_task(message)


def spoken_should_stream_live_deltas(
    *,
    spoken_mode: bool,
    message: str,
    task_state: dict[str, Any] | None = None,
) -> bool:
    """Chitchat can stream LIVE tokens; operator tasks wait for the typed final payload.

    A turn inside a task in progress (an email draft waiting for details, an
    approval, a running plan) waits too. LIVE may hand such a turn to the
    pending-task path after it has started talking, and that path then gives
    its own answer: the user heard the same clarification twice (live email
    test, 2026-10-11). Waiting keeps one answer per reply.
    """
    if not spoken_mode:
        return False
    if should_force_live_connector_pipeline(message):
        return False
    from app.services.conversation_tier import has_pending_task_state

    return not has_pending_task_state(task_state)


def resolve_voice_turn_routing(
    message: str,
    *,
    history: list[dict[str, Any]] | None = None,
    task_state: dict[str, Any] | None = None,
) -> tuple[Any, str]:
    """(ConversationTier, execution mode) for one voice turn.

    The one function every voice entry (Pipecat confirmed turn, speculative
    run, legacy HTTP duplex) uses, so the same final text and history always
    produce the same tier and mode.
    """
    from app.services.conversation_tier import (
        classify_conversation_tier,
        tier_to_execution_mode,
    )

    tier = classify_conversation_tier(message, history=history, task_state=task_state)
    return tier, tier_to_execution_mode(tier.tier)


def resolve_voice_session_intelligence_mode(
    message: str,
    *,
    history: list[dict[str, Any]] | None = None,
    task_state: dict[str, Any] | None = None,
) -> str:
    """Voice has no mode picker: light/medium run fast, deep runs the agent engine."""
    return resolve_voice_turn_routing(message, history=history, task_state=task_state)[1]


def resolve_default_text_intelligence_mode(message: str) -> str:
    """Text chat without a pinned mode: operator jobs match agent chat, the rest fast.

    Kept separate from the voice tier mapping so text routing does not change
    when the voice classifier does.
    """
    if should_keep_full_reasoning_for_spoken(message):
        return "agent"
    return "fast"
