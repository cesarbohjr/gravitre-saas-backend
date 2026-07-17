"""Tool result summarization — compress large connector payloads before LLM re-entry.

Keeps structured provenance available via `raw_ref` metadata; never drops error
signals. Prefer domain mappers when present; fall back to aggregate insights.
"""
from __future__ import annotations

from typing import Any

_LIST_KEYS = (
    "contacts",
    "companies",
    "deals",
    "tickets",
    "records",
    "channels",
    "issues",
    "items",
    "results",
    "rows",
    "owners",
    "users",
    "messages",
    "events",
)


def _list_payload(data: dict[str, Any]) -> tuple[str | None, list[Any]]:
    for key in _LIST_KEYS:
        value = data.get(key)
        if isinstance(value, list):
            return key, value
    search = data.get("search")
    if isinstance(search, dict):
        nested = search.get("results") or search.get("contacts") or search.get("items")
        if isinstance(nested, list):
            return "search.results", nested
    return None, []


def _sample_labels(rows: list[Any], *, limit: int = 5) -> list[str]:
    labels: list[str] = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            labels.append(str(row)[:80])
            continue
        props = row.get("properties") if isinstance(row.get("properties"), dict) else row
        for key in (
            "name",
            "dealname",
            "subject",
            "title",
            "email",
            "fullname",
            "key",
            "id",
            "firstname",
            "lastname",
        ):
            val = props.get(key) if isinstance(props, dict) else None
            if val:
                if key == "firstname":
                    last = (props.get("lastname") or "") if isinstance(props, dict) else ""
                    labels.append(f"{val} {last}".strip())
                else:
                    labels.append(str(val)[:80])
                break
        else:
            labels.append(str(row.get("id") or "record")[:80])
    return labels


def summarize_tool_payload(
    payload: Any,
    *,
    action: str | None = None,
    max_insights: int = 12,
    max_chars: int = 1600,
) -> dict[str, Any]:
    """Return compact insights for model context + optional user-facing summary."""
    if payload is None:
        return {
            "summary": "No tool payload.",
            "insights": [],
            "truncated": False,
            "record_count": 0,
        }

    if not isinstance(payload, dict):
        text = str(payload)
        truncated = len(text) > max_chars
        return {
            "summary": text[:max_chars] + ("…" if truncated else ""),
            "insights": [text[:200]] if text else [],
            "truncated": truncated,
            "record_count": 0,
        }

    if payload.get("success") is False or payload.get("error"):
        err = payload.get("error") or payload.get("message") or "tool failed"
        return {
            "summary": f"Tool error: {err}",
            "insights": [f"error: {err}"],
            "truncated": False,
            "record_count": 0,
            "error": True,
        }

    key, rows = _list_payload(payload)
    insights: list[str] = []
    if action:
        insights.append(f"action: {action}")

    if key is not None:
        count = len(rows)
        insights.append(f"{key}: {count} record(s)")
        for label in _sample_labels(rows, limit=min(5, max_insights)):
            insights.append(f"sample: {label}")
        # Lightweight aggregates for common CRM fields.
        statuses: dict[str, int] = {}
        for row in rows[:200]:
            if not isinstance(row, dict):
                continue
            props = row.get("properties") if isinstance(row.get("properties"), dict) else row
            if not isinstance(props, dict):
                continue
            st = props.get("hs_pipeline_stage") or props.get("dealstage") or props.get("status")
            if st:
                statuses[str(st)] = statuses.get(str(st), 0) + 1
        for st, n in sorted(statuses.items(), key=lambda kv: kv[1], reverse=True)[:4]:
            insights.append(f"status {st}: {n}")
        summary = f"{action or 'Tool'} returned {count} {key}."
        if count and insights:
            summary = f"{summary} Top samples: " + "; ".join(_sample_labels(rows, limit=3))
        return {
            "summary": summary[:max_chars],
            "insights": insights[:max_insights],
            "truncated": count > 12 or len(str(payload)) > max_chars,
            "record_count": count,
            "list_key": key,
        }

    # Scalar / nested object — keep small JSON slice.
    keep_keys = (
        "id",
        "status",
        "url",
        "name",
        "subject",
        "title",
        "count",
        "total",
        "message",
        "deal",
        "contact",
        "ticket",
        "issue",
        "channel",
    )
    compact = {k: payload[k] for k in keep_keys if k in payload}
    if not compact:
        compact = {k: payload[k] for k in list(payload.keys())[:8]}
    text = str(compact)
    truncated = len(str(payload)) > max_chars
    insights.append(f"fields: {', '.join(compact.keys())}" if compact else "empty object")
    return {
        "summary": text[:max_chars] + ("…" if truncated else ""),
        "insights": insights[:max_insights],
        "truncated": truncated,
        "record_count": 0,
        "compact": compact,
    }


def format_insights_for_model(summary: dict[str, Any]) -> str:
    """Single string block suitable for ReAct observations."""
    lines = [str(summary.get("summary") or "").strip()]
    for insight in summary.get("insights") or []:
        lines.append(f"- {insight}")
    text = "\n".join(line for line in lines if line)
    return text[:2000]
