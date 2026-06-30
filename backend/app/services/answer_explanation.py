"""Human-readable 'why this answer' summaries for assistant responses."""
from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.cache_service import get_cache_service
from app.services.rag_cache_helpers import SOURCE_SUMMARY_TTL_SECONDS, source_summary_cache_parts


def generate_answer_explanation(
    sources_used: list[dict[str, Any]],
    *,
    reasoning_trace: list[dict[str, Any]] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
    refined_query: str | None = None,
) -> str:
    """
    Short audit-friendly summary citing evidence sources — not chain-of-thought.
    """
    if not sources_used and not (reasoning_trace or []):
        return "This answer relied on general reasoning without retrieved internal documents."

    titles: list[str] = []
    for source in sources_used:
        label = str(source.get("source") or source.get("title") or source.get("kind") or "").strip()
        if label and label not in titles:
            titles.append(label)

    tool_names = [
        str(step.get("toolName") or step.get("tool_name") or step.get("action") or "")
        for step in (reasoning_trace or [])
        if step.get("toolName") or step.get("tool_name") or step.get("action")
    ]
    tool_counts = Counter(name for name in tool_names if name)

    parts: list[str] = []
    if titles:
        if len(titles) == 1:
            parts.append(f"This answer drew primarily on {titles[0]}.")
        else:
            parts.append(
                f"This answer drew on {len(titles)} internal sources, including {titles[0]} "
                f"and {titles[1] if len(titles) > 1 else 'other documents'}."
            )
        top = max(sources_used, key=lambda row: float(row.get("score") or 0.0), default=None)
        if top and float(top.get("score") or 0.0) >= 0.5:
            top_label = top.get("source") or top.get("title") or "one source"
            parts.append(f"{top_label} matched most strongly to your question.")
    if tool_counts:
        top_tool, count = tool_counts.most_common(1)[0]
        parts.append(f"Live data came from {top_tool} ({count} call{'s' if count != 1 else ''}).")
    if refined_query:
        parts.append("Retrieval used an expanded search query based on recent conversation context.")
    if conflicts:
        parts.append(
            f"{len(conflicts)} potential source conflict{'s' if len(conflicts) != 1 else ''} "
            "were flagged and weighed cautiously."
        )
    return " ".join(parts) if parts else "This answer combined retrieved context with tool results."


def generate_suggestion_explanation(
    suggestion: dict[str, Any],
) -> str:
    """Human-readable summary for v10 optimization suggestions — not chain-of-thought."""
    evidence = suggestion.get("evidence") if isinstance(suggestion.get("evidence"), dict) else {}
    source = str(evidence.get("source") or "platform analysis").strip()
    suggestion_type = str(suggestion.get("suggestion_type") or suggestion.get("suggestionType") or "suggestion")
    sample_size = evidence.get("sample_size") or evidence.get("sampleSize")
    parts = [
        f"This {suggestion_type.replace('_', ' ')} recommendation is based on {source}.",
    ]
    if sample_size:
        parts.append(f"It used {sample_size} observed samples before surfacing.")
    confidence_note = evidence.get("confidence_note") or evidence.get("confidenceNote")
    if confidence_note:
        parts.append(str(confidence_note))
    elif suggestion.get("estimated_impact") or suggestion.get("estimatedImpact"):
        parts.append(str(suggestion.get("estimated_impact") or suggestion.get("estimatedImpact")))
    else:
        parts.append("Review the cited evidence before applying any change.")
    return " ".join(parts)


async def generate_answer_explanation_cached(
    settings: Any,
    org_id: str,
    sources_used: list[dict[str, Any]],
    *,
    reasoning_trace: list[dict[str, Any]] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
    refined_query: str | None = None,
) -> str:
    cache = get_cache_service(settings)
    parts = source_summary_cache_parts(
        org_id,
        sources_used,
        conflict_count=len(conflicts or []),
        refined_query=refined_query,
    )
    cached = await cache.get("source_summary", *parts)
    if isinstance(cached, dict) and cached.get("text"):
        await cache.record_hit("source_summary")
        return str(cached["text"])
    await cache.record_miss("source_summary")
    text = generate_answer_explanation(
        sources_used,
        reasoning_trace=reasoning_trace,
        conflicts=conflicts,
        refined_query=refined_query,
    )
    await cache.set("source_summary", {"text": text}, SOURCE_SUMMARY_TTL_SECONDS, *parts)
    return text
