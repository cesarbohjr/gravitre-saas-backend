"""User-safe summary of the context a chat answer was built from.

The unified turn's knowledge step records a ``contextRanking`` (which sources
were selected, which were left out and why) for audit. This module turns that
record into something a user can read under "Why this answer?": plain source
names and kinds, freshness in words, and one sentence that says what was used
and what was skipped.

Rules:
- Only what the ranking actually recorded. No source, count or date is invented.
- No internal identifiers: labels that look like ids are replaced by the kind.
- Freshness words only when a real date was recorded for that source.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

MAX_USED_SOURCES = 8

# Source type -> (kind shown to users, plural noun used in the sentence).
_KIND_LABELS: dict[str, tuple[str, str, str]] = {
    "rag": ("Your knowledge", "document from your knowledge", "documents from your knowledge"),
    "knowledge_fabric": ("Gravitre library", "reference article", "reference articles"),
    "internet": ("Web", "web result", "web results"),
    "graph": ("Connected tools", "record from your connected tools", "records from your connected tools"),
    "connector_context": ("Connected tools", "record from your connected tools", "records from your connected tools"),
    "conversation_memory": ("Memory", "your conversation memory", "memory notes"),
    "agent_memory": ("Memory", "your agent memory", "memory notes"),
    "entity_graph": ("Org memory", "your company definitions", "company definition sets"),
    "org_context": ("Org memory", "your company profile", "company profile entries"),
    "customer_quote": ("Customer email", "customer email", "customer emails"),
    "account_interpretation": ("Customer sentiment", "customer sentiment summary", "customer sentiment summaries"),
    "account_measurement": ("Account health", "account health reading", "account health readings"),
    "work_state": ("Linked work", "linked work item", "linked work items"),
}

# Names the ranking writes when it has nothing better; shown as the kind instead.
_KIND_NAMES: dict[str, str] = {
    "conversation_memory": "Conversation and agent memory",
    "entity_graph": "Company definitions and relationships",
    "graph": "Records from your connected tools",
    "connector_context": "Records from your connected tools",
}

_ID_LIKE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    r"|(\b[0-9a-f]{12,}\b)"
    r"|(^[a-z_]+:[A-Za-z0-9_-]+$)",
    re.I,
)
_GENERIC_LABEL = re.compile(r"^(org document|[a-z_]+ source \d+)$", re.I)


def _kind(source_type: str) -> tuple[str, str, str]:
    return _KIND_LABELS.get(source_type, ("Other", "other source", "other sources"))


def _safe_name(source_type: str, label: Any) -> str:
    if source_type in _KIND_NAMES:
        return _KIND_NAMES[source_type]
    text = str(label or "").strip()
    if not text or _ID_LIKE.search(text) or _GENERIC_LABEL.match(text):
        return _kind(source_type)[0]
    return text[:120]


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _plural(n: int, unit: str) -> str:
    return f"{n} {unit}{'' if n == 1 else 's'}"


def freshness_words(value: Any, *, now: datetime | None = None) -> str | None:
    """'updated 2 hours ago' style wording for a recorded date; None when unknown."""
    when = _parse(value)
    if when is None:
        return None
    now = now or datetime.now(UTC)
    seconds = (now - when).total_seconds()
    if seconds < 0:
        return None
    # A bare date (no time) cannot honestly say hours.
    date_only = isinstance(value, str) and len(value.strip()) <= 10
    minutes = int(seconds // 60)
    hours = int(seconds // 3600)
    days = int(seconds // 86400)
    if date_only:
        if days < 1:
            return "updated today"
        if days < 2:
            return "updated yesterday"
    else:
        if minutes < 1:
            return "updated just now"
        if minutes < 60:
            return f"updated {_plural(minutes, 'minute')} ago"
        if hours < 24:
            return f"updated {_plural(hours, 'hour')} ago"
    if days < 14:
        return f"updated {_plural(max(1, days), 'day')} ago"
    if days < 60:
        return f"updated {_plural(days // 7, 'week')} ago"
    if days < 730:
        return f"updated {_plural(days // 30, 'month')} ago"
    return f"updated {_plural(days // 365, 'year')} ago"


def _join(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _count_phrase(n: int, singular: str, plural: str) -> str:
    if singular.startswith("your "):
        return singular
    return f"{n} {singular if n == 1 else plural}"


_SKIP_REASONS: dict[str, tuple[str, str, str]] = {
    # reason key -> (label shown in the list, sentence phrase for 1, for many)
    "out_of_date": ("Out of date", "1 out-of-date source", "{n} out-of-date sources"),
    "not_connected": (
        "From a tool that isn't connected",
        "1 source from a tool that isn't connected",
        "{n} sources from tools that aren't connected",
    ),
    "no_longer_available": (
        "Deleted or no longer available",
        "1 source that is no longer available",
        "{n} sources that are no longer available",
    ),
    "repeated": ("Repeated another source", "1 repeat", "{n} repeats"),
    "less_relevant": (
        "Less relevant to this question",
        "1 less relevant source",
        "{n} less relevant sources",
    ),
}


def build_user_context_sources(
    knowledge_meta: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Summarize ``unifiedTurnKnowledge`` meta for the user. None when nothing was recorded."""
    if not isinstance(knowledge_meta, dict) or not knowledge_meta:
        return None
    ranking = knowledge_meta.get("contextRanking")
    ranking = ranking if isinstance(ranking, dict) else {}

    skipped_counts: dict[str, int] = {}
    for row in ranking.get("excludedSources") or []:
        reason = str((row or {}).get("reason") or "") if isinstance(row, dict) else ""
        key = {
            "superseded": "out_of_date",
            "expired": "out_of_date",
            "duplicate": "repeated",
            "near_duplicate": "repeated",
            "budget": "less_relevant",
        }.get(reason)
        if key:
            skipped_counts[key] = skipped_counts.get(key, 0) + 1
    try:
        not_connected = int(knowledge_meta.get("competing_crm_hits_dropped") or 0)
    except (TypeError, ValueError):
        not_connected = 0
    if not_connected > 0:
        skipped_counts["not_connected"] = skipped_counts.get("not_connected", 0) + not_connected
    if knowledge_meta.get("org_rag_liveness_reason") is None:
        try:
            gone = int(knowledge_meta.get("org_rag_liveness_excluded") or 0)
        except (TypeError, ValueError):
            gone = 0
        if gone > 0:
            skipped_counts["no_longer_available"] = gone

    selected = ranking.get("selectedSources") if isinstance(ranking.get("selectedSources"), list) else []
    dates = ranking.get("selectedSourcesAsOf") if isinstance(ranking.get("selectedSourcesAsOf"), list) else []
    used: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    by_type: dict[str, int] = {}
    for index, row in enumerate(selected):
        if not isinstance(row, dict):
            continue
        source_type = str(row.get("type") or "")
        name = _safe_name(source_type, row.get("label") or row.get("citation"))
        kind = _kind(source_type)[0]
        if (name, kind) in seen:
            continue
        seen.add((name, kind))
        by_type[source_type] = by_type.get(source_type, 0) + 1
        item: dict[str, Any] = {"name": name, "kind": kind}
        words = freshness_words(dates[index] if index < len(dates) else None, now=now)
        if words:
            item["freshness"] = words
        used.append(item)

    skipped = [
        {"reason": key, "label": _SKIP_REASONS[key][0], "count": count}
        for key, count in skipped_counts.items()
        if count > 0
    ]

    if not used and not skipped:
        if knowledge_meta.get("skipped") in {"no_hits", "no_retrieval_hits"}:
            return {
                "summary": (
                    "No documents, memory or connected-tool records matched this question, "
                    "so this answer is based on the conversation and any tools it used."
                ),
                "used": [],
                "skipped": [],
            }
        return None

    if used:
        parts = [
            _count_phrase(count, _kind(source_type)[1], _kind(source_type)[2])
            for source_type, count in by_type.items()
        ]
        sentence = f"Used {_join(parts)}"
    else:
        sentence = "Didn't use any saved sources"
    skip_parts = [
        _SKIP_REASONS[row["reason"]][1]
        if row["count"] == 1
        else _SKIP_REASONS[row["reason"]][2].format(n=row["count"])
        for row in skipped
    ]
    if skip_parts:
        sentence += f", and left out {_join(skip_parts)}"
    sentence += "."

    return {
        "summary": sentence,
        "used": used[:MAX_USED_SOURCES],
        "usedCount": len(used),
        "skipped": skipped,
        "freshnessChecked": bool(ranking.get("freshnessApplied")),
    }
