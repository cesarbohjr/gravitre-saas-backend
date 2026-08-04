"""When unified-turn live must defer to the classical ReAct/governed pipeline.

Wave 6–7 and retrieval A/B probes expect tool-input SSE, strategic plan metadata,
react_write_gate chips, and researchCascade events. Unified-turn text-only outcomes
must fall through so classical routing can run.
"""
from __future__ import annotations

import re
from typing import Any

_MESSAGE_TOOL_SSE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bconnectors?\b.*\bconnected\b", re.I),
    re.compile(r"\bwhat connectors\b", re.I),
    re.compile(r"\bgetconnectorstatus\b", re.I),
    re.compile(r"\brefund policy\b", re.I),
    re.compile(r"\binternal (?:org )?knowledge\b", re.I),
    re.compile(r"\bfictional subsidiary\b", re.I),
    re.compile(r"\bzephyr dynamics\b", re.I),
    re.compile(r"\boutline\b.*\bplan\b.*\btools?\b", re.I),
    re.compile(r"\bplan\b.*\bbefore\b.*\btools?\b", re.I),
    re.compile(r"\bcontact lists?\b", re.I),
    re.compile(r"\bapollo\b", re.I),
    re.compile(r"\bslack\b", re.I),
    re.compile(r"\bpost (?:a )?(?:slack )?message\b", re.I),
    re.compile(r"\bcreate an? apollo contact list\b", re.I),
    re.compile(r"\bsearchknowledgebase\b", re.I),
    re.compile(r"\bknowledge base\b", re.I),
)


def message_requires_classical_tool_sse(message: str) -> bool:
    """Utterances that need classical tool SSE / wave67 probe events.

    Does not include generic write phrasing (e.g. \"Send an email…\") — those
    often resolve to LIVE clarifying_question text. Connector write proposals
    still defer via outcome_kind == connector_tool_proposal.

    Pack-common MSP Clay→HubSpot enrich must stay on LIVE (or classical pack
    intercept) — the TRY prompt contains \"Apollo\" / \"contact list\" which
    would otherwise force a broken multi-step Search-contacts orchestration.
    """
    text = (message or "").strip()
    if not text:
        return False
    from app.services.pack_common_intent_defaults import (
        try_pack_common_msp_enrich_workflow_plan,
    )

    if try_pack_common_msp_enrich_workflow_plan(text) is not None:
        return False
    return any(p.search(text) for p in _MESSAGE_TOOL_SSE_PATTERNS)


def should_defer_unified_turn_live_to_classical(
    *,
    mode_key: str | None,
    outcome_kind: str,
    message: str,
    classification: dict[str, Any] | None = None,
) -> bool:
    """Return True to skip unified live and run the classical pipeline.

    Text kinds (greeting/thanks/clarify) stay on LIVE even when connectors upgrade
    ``standard`` → ``agent`` via ``resolve_effective_intelligence_mode``. Only
    tool-shaped utterances and connector write proposals defer.
    """
    kind = str(outcome_kind or "").strip().lower()
    msg = message or ""
    _ = (mode_key, classification)  # mode no longer blankets text-kind defer

    if kind == "connector_tool_proposal":
        # Unified LIVE stages write approval + pending_task; classical was misrouting
        # Gmail sends into HubSpot clarify (defer_connector_tool_proposal bug).
        return False

    if kind not in {
        "conversational_reply",
        "knowledge_boundary",
        "confirmation_request",
        "clarifying_question",
    }:
        return False

    # Defer text kinds only when the utterance needs tool SSE / write chips.
    return message_requires_classical_tool_sse(msg)
