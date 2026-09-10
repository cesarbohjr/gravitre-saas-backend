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


def should_skip_unified_live_guards(
    *,
    spoken_mode: bool,
    reasoning_depth: str,
    has_pending: bool,
    message: str,
) -> bool:
    """Voice latency skip of channel/meta/pending resolvers — never for operator tasks."""
    if not spoken_mode:
        return False
    if has_pending:
        return False
    if str(reasoning_depth or "").strip().lower() != "conversational":
        return False
    if looks_like_operator_task(message) or should_keep_full_reasoning_for_spoken(message):
        return False
    return True


def use_spoken_lite_path(
    *,
    spoken_mode: bool,
    routing_tier: str,
    message: str,
) -> bool:
    """Skip understand/classify enrichments for spoken chitchat only."""
    if not spoken_mode:
        return False
    if str(routing_tier or "").strip().lower() != "simple":
        return False
    if should_keep_full_reasoning_for_spoken(message):
        return False
    try:
        from app.services.conversational_planning_engine import is_direct_connector_write_intent

        if is_direct_connector_write_intent(message or ""):
            return False
    except Exception:  # noqa: BLE001
        pass
    return True


def should_force_live_connector_pipeline(message: str) -> bool:
    """LIVE must not answer real jobs in spoken prose; use orch/classical instead."""
    return looks_like_operator_task(message)


def spoken_should_stream_live_deltas(*, spoken_mode: bool, message: str) -> bool:
    """Chitchat can stream LIVE tokens; operator tasks wait for the typed final payload."""
    if not spoken_mode:
        return False
    if should_force_live_connector_pipeline(message):
        return False
    return True
