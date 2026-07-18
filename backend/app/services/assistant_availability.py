"""Assistant availability heuristics — bounded answers when KB and web search are empty."""
from __future__ import annotations

import re
from typing import Any

from app.config import Settings

_EXTERNAL_PATTERNS = (
    re.compile(r"\b(what is|who is|tell me about|explain|describe)\b", re.I),
    re.compile(r"\b(latest|current|today'?s?|news|market|industry|trends?)\b", re.I),
    re.compile(r"\bhow (?:does|do|is|are)\b", re.I),
)

_ORG_SCOPED_PATTERNS = (
    re.compile(r"\b(our|my org(?:anization)?|my team|we have|our crm|our workflow|our connector)\b", re.I),
    re.compile(r"\b(in hubspot|in salesforce|in our)\b", re.I),
)

_WEB_TOOL_NAMES = frozenset({"searchWeb", "search_web", "web_search"})


def is_web_search_configured(settings: Settings) -> bool:
    """True when a web research provider is configured (respects governance when flag off for cascade)."""
    from app.services.web_research import is_web_research_provider_configured

    return is_web_research_provider_configured(settings)


def is_internet_research_governed_and_available(settings: Settings) -> bool:
    from app.services.adaptive_research_cascade import _internet_research_allowed

    return _internet_research_allowed(settings)


def rag_sources_effectively_empty(rag_sources: list[dict[str, Any]] | None) -> bool:
    if not rag_sources:
        return True
    for row in rag_sources:
        content = str(row.get("content") or row.get("snippet") or "").strip()
        if content:
            return False
    return True


def is_external_or_general_question(query: str) -> bool:
    cleaned = (query or "").strip()
    if not cleaned:
        return False
    if any(pattern.search(cleaned) for pattern in _ORG_SCOPED_PATTERNS):
        return False
    if any(pattern.search(cleaned) for pattern in _EXTERNAL_PATTERNS):
        return True
    if cleaned.endswith("?") and len(cleaned.split()) <= 14:
        return True
    return False


def web_search_failed_in_tool_results(tool_results: list[dict[str, Any]] | None) -> bool:
    for row in tool_results or []:
        name = str(row.get("name") or "")
        if name not in _WEB_TOOL_NAMES:
            continue
        output = row.get("output")
        if not isinstance(output, dict):
            continue
        if output.get("error"):
            return True
        if output.get("success") is False:
            return True
    return False


def _real_connectors(connected_integrations: list[str] | None) -> list[str]:
    values = [str(item).strip() for item in (connected_integrations or []) if str(item).strip()]
    return [value for value in values if value.lower() != "platform"]


def build_bounded_unavailable_answer(
    *,
    web_configured: bool,
    web_attempted: bool,
    connected_integrations: list[str] | None = None,
) -> str:
    lines = [
        "I can't answer that with verified information right now.",
        "",
        "Your organization's knowledge base did not return relevant excerpts for this question.",
    ]
    if web_attempted:
        if web_configured:
            lines.append("Web search ran but did not return usable results.")
        else:
            lines.append(
                "Web search is not configured in this environment (enable INTERNET_RESEARCH_ENABLED "
                "and configure Google grounding or TAVILY_API_KEY on the backend)."
            )
    elif not web_configured:
        lines.append(
            "Web search is not configured in this environment (enable INTERNET_RESEARCH_ENABLED "
            "and configure Google grounding or TAVILY_API_KEY on the backend)."
        )

    if not _real_connectors(connected_integrations):
        lines.extend(
            [
                "",
                "For CRM, analytics, or synced document answers, connect integrations at /connectors "
                "and enable knowledge sync under Sources.",
            ]
        )

    lines.extend(
        [
            "",
            "For product questions about Gravitre, see /docs or ask about Assistant, Workflows, and Connectors.",
        ]
    )
    return "\n".join(lines)


def should_short_circuit_before_generation(
    *,
    query: str,
    rag_sources: list[dict[str, Any]] | None,
    settings: Settings,
    permitted_registry: set[str] | frozenset[str] | list[str] | None,
) -> bool:
    if not is_external_or_general_question(query):
        return False
    if not rag_sources_effectively_empty(rag_sources):
        return False
    if is_web_search_configured(settings):
        return False
    permitted = {str(item) for item in (permitted_registry or [])}
    return "web_search" in permitted


def apply_bounded_answer_if_needed(
    answer: str,
    *,
    query: str,
    rag_sources: list[dict[str, Any]] | None,
    tool_results: list[dict[str, Any]] | None,
    settings: Settings,
    connected_integrations: list[str] | None = None,
) -> str:
    if not is_external_or_general_question(query):
        return answer
    if not rag_sources_effectively_empty(rag_sources):
        return answer

    web_configured = is_web_search_configured(settings)
    web_failed = web_search_failed_in_tool_results(tool_results)
    if web_configured and not web_failed:
        return answer

    return build_bounded_unavailable_answer(
        web_configured=web_configured,
        web_attempted=web_failed or not web_configured,
        connected_integrations=connected_integrations,
    )
