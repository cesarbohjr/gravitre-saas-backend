"""Convert structured/JSON model output into user-facing plain English."""
from __future__ import annotations

import json
import re
from typing import Any

_CODE_FENCE = re.compile(r"^```(?:json)?\s*([\s\S]*?)```$", re.I)
_NAME_FIELD = re.compile(r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"')
_SUMMARY_FIELD = re.compile(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"')
_ACTION_FIELD = re.compile(r'"(?:action|tool)"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _strip_fences(text: str) -> str:
    trimmed = text.strip()
    match = _CODE_FENCE.match(trimmed)
    if match:
        return match.group(1).strip()
    return trimmed


def _humanize_action_token(action: str) -> str:
    token = action.strip().replace("_", " ").replace(".", " ")
    if not token:
        return "No action taken"
    return token[0].upper() + token[1:] if token else token


def _format_decision(decision: Any) -> str:
    if decision is None:
        return ""
    if isinstance(decision, str):
        return decision.strip()
    if not isinstance(decision, dict):
        return str(decision).strip()
    parts: list[str] = []
    action = decision.get("action")
    reason = decision.get("reason")
    if isinstance(action, str) and action.strip():
        parts.append(_humanize_action_token(action))
    if isinstance(reason, str) and reason.strip():
        parts.append(reason.strip())
    for key in ("message", "summary", "explanation"):
        value = decision.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return " ".join(parts).strip()


def _format_recommended_actions(actions: Any) -> str:
    if not isinstance(actions, list):
        return ""
    lines: list[str] = []
    for item in actions[:6]:
        if isinstance(item, str) and item.strip():
            lines.append(f"• {item.strip()}")
        elif isinstance(item, dict):
            label = item.get("label") or item.get("title") or item.get("action")
            if isinstance(label, str) and label.strip():
                lines.append(f"• {label.strip()}")
    if not lines:
        return ""
    return "Recommended next steps:\n" + "\n".join(lines)


def _looks_like_tool_envelope(value: dict[str, Any]) -> bool:
    keys = set(value.keys())
    return bool(keys & {"tool", "action", "success", "result", "data"}) and (
        "result" in keys or "data" in keys or "tool" in keys or "action" in keys
    )


def _humanize_tool_envelope(value: dict[str, Any]) -> str:
    from app.services.tool_result_summarizer import summarize_tool_payload

    summary = summarize_tool_payload(value)
    text = str(summary.get("summary") or "").strip()
    return text


def _humanize_list_of_records(rows: list[Any]) -> str:
    from app.services.tool_result_summarizer import summarize_tool_payload

    summary = summarize_tool_payload(rows)
    return str(summary.get("summary") or "").strip()


def _extract_from_partial_json(text: str) -> str:
    """Best-effort plain language when JSON is truncated / unparseable."""
    summary = _SUMMARY_FIELD.search(text)
    if summary:
        return summary.group(1).replace('\\"', '"').strip()
    names = [_m.group(1).replace('\\"', '"').strip() for _m in _NAME_FIELD.finditer(text)]
    names = [n for n in names if n]
    action_m = _ACTION_FIELD.search(text)
    action = _humanize_action_token(action_m.group(1)) if action_m else "Tool"
    if names:
        shown = ", ".join(names[:5])
        more = f" (+{len(names) - 5} more)" if len(names) > 5 else ""
        return f"{action} returned {len(names)} item(s). Including: {shown}{more}."
    if '"success"' in text and action_m:
        return f"{action} completed. Structured details were returned — ask if you need the next step."
    return ""


def format_plain_english(value: Any, *, fallback: str = "") -> str:
    """Best-effort conversion of model/handoff payloads to readable prose."""
    if value is None:
        return fallback
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        humanized_list = _humanize_list_of_records(value)
        if humanized_list:
            return humanized_list
        return fallback or "Details are available in Gravitre — ask if you want help with next steps."
    if isinstance(value, dict):
        if _looks_like_tool_envelope(value):
            tool_text = _humanize_tool_envelope(value)
            if tool_text:
                return tool_text
        parts: list[str] = []
        for key in ("summary", "answer", "message", "explanation", "reason", "description"):
            part = value.get(key)
            if isinstance(part, str) and part.strip():
                # Nested JSON strings inside summary/answer
                nested = format_plain_english(part, fallback=part.strip())
                parts.append(nested.strip())
        decision_text = _format_decision(value.get("decision"))
        if decision_text:
            parts.append(decision_text)
        actions_text = _format_recommended_actions(
            value.get("recommended_actions") or value.get("recommendedActions")
        )
        if actions_text:
            parts.append(actions_text)
        confidence = value.get("confidence")
        if isinstance(confidence, (int, float)) and confidence and not parts:
            parts.append(f"Confidence: {int(confidence)}%.")
        if parts:
            return "\n\n".join(parts).strip()
        # Last resort: treat whole dict as tool-ish payload
        tool_text = _humanize_tool_envelope(value)
        if tool_text and "{" not in tool_text:
            return tool_text
        return fallback or "Details are available in Gravitre — ask if you want help with next steps."

    text = _strip_fences(str(value).strip())
    if not text:
        return fallback

    if text.startswith("{") or text.startswith("["):
        try:
            parsed = json.loads(text)
            converted = format_plain_english(parsed, fallback=fallback)
            if converted and not converted.strip().startswith(("{", "[")):
                return converted
        except json.JSONDecodeError:
            partial = _extract_from_partial_json(text)
            if partial:
                return partial

    if text.startswith('"') and text.endswith('"'):
        try:
            unquoted = json.loads(text)
            if isinstance(unquoted, str):
                return format_plain_english(unquoted, fallback=fallback)
        except json.JSONDecodeError:
            pass

    # Never surface raw JSON blobs to operators.
    if text.lstrip().startswith(("{", "[")):
        partial = _extract_from_partial_json(text)
        if partial:
            return partial
        return fallback or "Structured tool results came back — ask if you want a plain-language summary."

    return text
