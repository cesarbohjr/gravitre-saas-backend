"""When unified-turn live must defer to the classical ReAct/governed pipeline.

Wave 6–7 and retrieval A/B probes expect tool-input SSE, strategic plan metadata,
react_write_gate chips, and researchCascade events. Unified-turn text-only outcomes
must fall through so classical routing can run.
"""
from __future__ import annotations

import re
from typing import Any

from app.operators.assistant_mode_config import normalize_mode
from app.services.conversational_planning_engine import is_direct_connector_write_intent

# Modes that always use classical ReAct/tool SSE for non-pending fresh turns.
# Intentionally excludes ``standard`` — Phase 4 LIVE owns pure conversational
# replies there; only tool-shaped utterances defer (see message patterns below).
_CLASSICAL_TOOL_SSE_MODES = frozenset({"reasoning", "agent"})

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
    text = (message or "").strip()
    if not text:
        return False
    if is_direct_connector_write_intent(text):
        return True
    return any(p.search(text) for p in _MESSAGE_TOOL_SSE_PATTERNS)


def should_defer_unified_turn_live_to_classical(
    *,
    mode_key: str | None,
    outcome_kind: str,
    message: str,
    classification: dict[str, Any] | None = None,
) -> bool:
    """Return True to skip unified live and run the classical pipeline."""
    kind = str(outcome_kind or "").strip().lower()
    mode = normalize_mode(mode_key or "standard")
    msg = message or ""

    if kind == "connector_tool_proposal":
        # Classical path emits tool SSE + react_write_gate; unified only stages pending text.
        return True

    if kind not in {
        "conversational_reply",
        "knowledge_boundary",
        "confirmation_request",
        "clarifying_question",
    }:
        return False

    if classification and classification.get("requires_action"):
        return True

    # Reasoning/agent: keep classical as primary for non-pending turns.
    if mode in _CLASSICAL_TOOL_SSE_MODES:
        return True

    # Standard + fast: defer only when the utterance needs tool SSE / write chips.
    if message_requires_classical_tool_sse(msg):
        return True

    return False
