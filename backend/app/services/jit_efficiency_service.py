"""3.0-B JIT context/tool efficiency audit samples.

Best-effort ``audit_events`` writes for eligible-tool namespace and context
include/exclude profiles. Never raises — must not block turns.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

TOOL_NAMESPACE_ACTION = "runtime.jit.tool_namespace"
CONTEXT_PROFILE_ACTION = "runtime.jit.context_profile"


def _write(
    settings: Any,
    *,
    org_id: str,
    user_id: str | None,
    conversation_id: str | None,
    action: str,
    payload: dict[str, Any],
) -> None:
    if not org_id or not user_id:
        logger.debug("jit_efficiency_sample_skipped action=%s reason=missing_org_or_user", action)
        return
    try:
        from app.workflows.audit import write_audit_event
        from app.workflows.repository import get_supabase_client

        client = get_supabase_client(settings)
        write_audit_event(
            client,
            org_id,
            user_id,
            action,
            "conversation",
            conversation_id or org_id,
            payload,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("jit_efficiency_sample_write_failed action=%s error=%s", action, exc)


def _tool_names_sample(tools: list[Any] | None, *, limit: int = 20) -> list[str]:
    names: list[str] = []
    for tool in tools or []:
        fn = tool.get("function") if isinstance(tool, dict) else None
        name = ""
        if isinstance(fn, dict):
            name = str(fn.get("name") or "").strip()
        if not name and isinstance(tool, dict):
            name = str(tool.get("name") or "").strip()
        if name:
            names.append(name)
        if len(names) >= limit:
            break
    return names


def record_jit_tool_namespace(
    settings: Any,
    *,
    org_id: str,
    user_id: str | None,
    conversation_id: str | None,
    tool_stats: dict[str, Any] | None,
    classification: dict[str, Any] | None = None,
    visible_tools: list[Any] | None = None,
    narrow_ms: int | None = None,
    payload_bytes: int | None = None,
    spoken_mode: bool = False,
) -> None:
    """Eligible-tool namespace sample for one unified turn."""
    stats = dict(tool_stats or {})
    cap_id = str((classification or {}).get("capability_id") or "").strip() or None
    payload: dict[str, Any] = {
        "totalTools": stats.get("totalTools"),
        "visibleTools": stats.get("visibleTools"),
        "catalogTools": stats.get("catalogTools"),
        "retrievalMethod": stats.get("retrievalMethod"),
        "embeddingToolRetrieval": stats.get("embeddingToolRetrieval"),
        "focusedConnectors": stats.get("focusedConnectors"),
        "actionRequired": stats.get("actionRequired"),
        "capabilityId": cap_id,
        "eligiblePrefixesApplied": bool(cap_id),
        "spokenChatNoTools": bool(stats.get("spokenChatNoTools")),
        "spokenMode": bool(spoken_mode),
        "narrowMs": narrow_ms,
        "payloadBytes": payload_bytes,
        "toolNamesSample": _tool_names_sample(visible_tools),
    }
    for key in (
        "topSimilarity",
        "embeddingCandidateCount",
        "capabilityToolsInjected",
        "executeNowDropped",
        "embeddingFallbackReason",
        "embeddingSkippedReason",
    ):
        if key in stats and stats[key] is not None:
            payload[key] = stats[key]
    _write(
        settings,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        action=TOOL_NAMESPACE_ACTION,
        payload=payload,
    )


def record_jit_context_profile(
    settings: Any,
    *,
    org_id: str,
    user_id: str | None,
    conversation_id: str | None,
    context_ranking: dict[str, Any] | None,
    classification: dict[str, Any] | None = None,
    spoken_mode: bool = False,
) -> None:
    """JIT context include/exclude profile for one unified turn."""
    ranking = dict(context_ranking or {})
    if not ranking:
        return
    cap_id = str((classification or {}).get("capability_id") or "").strip() or None
    payload: dict[str, Any] = {
        "mode": ranking.get("mode"),
        "capabilityId": cap_id,
        "candidateCount": ranking.get("candidateCount"),
        "selectedCount": ranking.get("selectedCount"),
        "duplicateCount": ranking.get("duplicateCount"),
        "tokenBudget": ranking.get("tokenBudget"),
        "evidenceTokenBudget": ranking.get("evidenceTokenBudget"),
        "tokensUsed": ranking.get("tokensUsed"),
        "advisoryTokens": ranking.get("advisoryTokens"),
        "blockOverheadTokens": ranking.get("blockOverheadTokens"),
        "selectedByKind": ranking.get("selectedByKind"),
        "tokensByKind": ranking.get("tokensByKind"),
        "excludedSources": ranking.get("excludedSources"),
        "selectedSourceIds": ranking.get("selectedSourceIds"),
        "legacyPromptChars": ranking.get("legacyPromptChars"),
        "rankedPromptChars": ranking.get("rankedPromptChars"),
        "managedSupplementalSections": ranking.get("managedSupplementalSections"),
        "spokenMode": bool(spoken_mode),
    }
    _write(
        settings,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        action=CONTEXT_PROFILE_ACTION,
        payload=payload,
    )
