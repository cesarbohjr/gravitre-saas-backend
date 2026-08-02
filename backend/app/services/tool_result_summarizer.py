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
    "result",
    "rows",
    "owners",
    "users",
    "messages",
    "events",
    "lists",
    "labels",
    "organizations",
    "people",
)


def _unwrap_tool_envelope(payload: dict[str, Any]) -> tuple[dict[str, Any] | list[Any] | Any, str | None]:
    """Peel ``{success, tool, action, result|data}`` wrappers used by connector invokes."""
    action = payload.get("action") or payload.get("tool")
    action_s = str(action).strip() if action else None
    if "result" in payload or "data" in payload:
        inner = payload.get("result") if "result" in payload else payload.get("data")
        return inner, action_s
    return payload, action_s


def _humanize_action_label(action: str | None) -> str:
    if not action:
        return "Tool"
    token = str(action).replace("_", " ").replace(".", " ").strip()
    return token[:1].upper() + token[1:] if token else "Tool"


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

    resolved_action = action
    working: Any = payload
    if isinstance(payload, dict) and (
        payload.get("tool") is not None
        or payload.get("action") is not None
        or "result" in payload
        or "data" in payload
    ):
        working, envelope_action = _unwrap_tool_envelope(payload)
        resolved_action = resolved_action or envelope_action
        if payload.get("success") is False or payload.get("error"):
            err = payload.get("error") or payload.get("message") or "tool failed"
            return {
                "summary": f"Tool error: {err}",
                "insights": [f"error: {err}"],
                "truncated": False,
                "record_count": 0,
                "error": True,
            }

    if isinstance(working, list):
        labels = _sample_labels(working, limit=min(5, max_insights))
        count = len(working)
        label = _humanize_action_label(resolved_action)
        summary = f"{label} returned {count} record(s)."
        if labels:
            summary = f"{summary} Including: {'; '.join(labels)}."
        return {
            "summary": summary[:max_chars],
            "insights": [f"sample: {x}" for x in labels][:max_insights],
            "truncated": count > 12,
            "record_count": count,
            "list_key": "result",
        }

    if not isinstance(working, dict):
        text = str(working)
        truncated = len(text) > max_chars
        return {
            "summary": text[:max_chars] + ("…" if truncated else ""),
            "insights": [text[:200]] if text else [],
            "truncated": truncated,
            "record_count": 0,
        }

    if working.get("success") is False or working.get("error"):
        err = working.get("error") or working.get("message") or "tool failed"
        return {
            "summary": f"Tool error: {err}",
            "insights": [f"error: {err}"],
            "truncated": False,
            "record_count": 0,
            "error": True,
        }

    key, rows = _list_payload(working)
    insights: list[str] = []
    action_label = _humanize_action_label(resolved_action)

    if key is not None:
        count = len(rows)
        insights.append(f"{key}: {count} record(s)")
        samples = _sample_labels(rows, limit=min(5, max_insights))
        for label in samples:
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
        summary = f"{action_label} returned {count} {key}."
        if samples:
            summary = f"{summary} Including: {'; '.join(samples[:3])}."
        return {
            "summary": summary[:max_chars],
            "insights": insights[:max_insights],
            "truncated": count > 12 or len(str(working)) > max_chars,
            "record_count": count,
            "list_key": key,
        }

    # Scalar / nested object — prefer human labels over raw dict dumps.
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
    compact = {k: working[k] for k in keep_keys if k in working}
    if not compact:
        compact = {k: working[k] for k in list(working.keys())[:8]}
    label_bits: list[str] = []
    for key in ("name", "title", "subject", "message", "status", "count", "total"):
        if key in compact and compact[key] not in (None, ""):
            label_bits.append(f"{key}={compact[key]}")
    if label_bits:
        summary = f"{action_label}: " + ", ".join(label_bits) + "."
    else:
        summary = f"{action_label} completed successfully."
    truncated = len(str(working)) > max_chars
    return {
        "summary": summary[:max_chars],
        "insights": [f"fields: {', '.join(compact.keys())}" if compact else "empty object"][:max_insights],
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
