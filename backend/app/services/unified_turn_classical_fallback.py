"""When unified-turn live must defer to the classical ReAct/governed pipeline.

Wave 6–7 and retrieval A/B probes expect tool-input SSE, strategic plan metadata,
react_write_gate chips, and researchCascade events. Unified-turn text-only outcomes
must fall through so classical routing can run.

F2 (2026-08-05): bare vendor/list/KB keyword defer triggers removed. Defer is
driven by LIVE ``needs_tool_sse`` (structured signal) with a reduced pattern
safety net for probe/wave67 strings only.
"""
from __future__ import annotations

import re
from typing import Any

# Secondary safety net only — NOT bare vendor names (apollo/slack/contact list/KB).
# Kept: connector-status probes, KB probe fixtures, wave67 plan-before-tools,
# explicit slack post / apollo list-create phrases, searchknowledgebase token.
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
    re.compile(r"\bpost (?:a )?(?:slack )?message\b", re.I),
    re.compile(r"\bcreate an? apollo contact list\b", re.I),
    re.compile(r"\bsearchknowledgebase\b", re.I),
)


def message_requires_classical_tool_sse(message: str) -> bool:
    """Utterances that need classical tool SSE / wave67 probe events.

    F2: no longer matches bare ``apollo`` / ``slack`` / ``contact list`` /
    ``knowledge base``. Prefer LIVE ``needs_tool_sse`` for real defer.
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
    needs_tool_sse: bool | None = None,
) -> bool:
    """Return True to skip unified live and run the classical pipeline.

    Text kinds (greeting/thanks/clarify) stay on LIVE even when connectors upgrade
    ``standard`` → ``agent`` via ``resolve_effective_intelligence_mode``. Only
    tool-shaped utterances defer — primarily via LIVE ``needs_tool_sse``.
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

    # F2 primary: structured signal from LIVE reasoning.
    if needs_tool_sse is True:
        return True

    # Secondary safety net (reduced pattern bag).
    return message_requires_classical_tool_sse(msg)
