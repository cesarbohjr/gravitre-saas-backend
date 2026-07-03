"""Convert structured/JSON model output into user-facing plain English."""
from __future__ import annotations

import json
import re
from typing import Any

_CODE_FENCE = re.compile(r"^```(?:json)?\s*([\s\S]*?)```$", re.I)


def _strip_fences(text: str) -> str:
    trimmed = text.strip()
    match = _CODE_FENCE.match(trimmed)
    if match:
        return match.group(1).strip()
    return trimmed


def _humanize_action_token(action: str) -> str:
    token = action.strip().replace("_", " ")
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


def format_plain_english(value: Any, *, fallback: str = "") -> str:
    """Best-effort conversion of model/handoff payloads to readable prose."""
    if value is None:
        return fallback
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        parts: list[str] = []
        for key in ("summary", "answer", "message", "explanation", "reason", "description"):
            part = value.get(key)
            if isinstance(part, str) and part.strip():
                parts.append(part.strip())
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
        return fallback or "Details are available in Gravitre — ask if you want help with next steps."

    text = _strip_fences(str(value).strip())
    if not text:
        return fallback

    if text.startswith("{") or text.startswith("["):
        try:
            parsed = json.loads(text)
            converted = format_plain_english(parsed, fallback=fallback)
            if converted:
                return converted
        except json.JSONDecodeError:
            partial = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if partial:
                return partial.group(1).replace('\\"', '"').strip()

    if text.startswith('"') and text.endswith('"'):
        try:
            unquoted = json.loads(text)
            if isinstance(unquoted, str):
                return format_plain_english(unquoted, fallback=fallback)
        except json.JSONDecodeError:
            pass

    return text
