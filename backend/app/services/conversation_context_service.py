"""Conversation context window management (STA-146 / AI-014).

When estimated tokens exceed 80% of the configured context window, summarize the
oldest half of history and keep the summary on the conversations row.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.core.logging import get_logger
from app.services.model_router import TaskType, get_model_router

logger = get_logger(__name__)

_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


def estimate_message_list_tokens(messages: list[dict[str, Any]]) -> int:
    return sum(estimate_tokens(str(message.get("content") or "")) for message in messages)


def context_window_tokens(settings: Settings) -> int:
    value = int(getattr(settings, "assistant_context_window_tokens", 0) or 128_000)
    return max(256, value)


def summarize_threshold_ratio(settings: Settings) -> float:
    value = float(getattr(settings, "assistant_context_summarize_threshold", 0.8) or 0.8)
    return min(max(value, 0.5), 0.95)


def format_summary_block(summary: str | None) -> str:
    cleaned = (summary or "").strip()
    if not cleaned:
        return ""
    return (
        "\n\n## Prior conversation summary\n"
        f"{cleaned}\n"
        "(Older turns were summarized to save context.)"
    )


def _format_turns_for_summary(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for message in messages:
        role = str(message.get("role") or "user").upper()
        content = str(message.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


@dataclass
class PreparedConversationContext:
    messages: list[dict[str, Any]]
    summary: str | None
    summary_updated: bool


async def maybe_summarize_history(
    *,
    history: list[dict[str, Any]],
    system_prompt: str,
    prompt: str,
    tool_messages: list[dict[str, Any]] | None,
    existing_summary: str | None,
    org_id: str,
    settings: Settings,
) -> PreparedConversationContext:
    """Return trimmed history and optional rolling summary."""
    summary = (existing_summary or "").strip() or None
    tool_messages = tool_messages or []

    def total_tokens(active_history: list[dict[str, Any]]) -> int:
        parts = [
            system_prompt,
            prompt,
            summary or "",
            *_message_contents(active_history),
            *_message_contents(tool_messages),
        ]
        return sum(estimate_tokens(part) for part in parts)

    window = context_window_tokens(settings)
    threshold = int(window * summarize_threshold_ratio(settings))

    if total_tokens(history) <= threshold:
        return PreparedConversationContext(messages=list(history), summary=summary, summary_updated=False)

    if len(history) < 2:
        return PreparedConversationContext(messages=list(history), summary=summary, summary_updated=False)

    split_at = max(1, len(history) // 2)
    oldest = history[:split_at]
    recent = history[split_at:]
    transcript = _format_turns_for_summary(oldest)
    if not transcript.strip():
        return PreparedConversationContext(messages=list(recent), summary=summary, summary_updated=False)

    router = get_model_router()
    summary_prompt = "Summarize the conversation history below for future assistant context.\n"
    summary_prompt += "Preserve decisions, names, metrics, open tasks, and unresolved questions.\n\n"
    if summary:
        summary_prompt += f"Existing summary to extend:\n{summary}\n\nNew turns to fold in:\n{transcript}"
    else:
        summary_prompt += transcript

    try:
        result = await router.complete(
            task_type=TaskType.SUMMARIZATION,
            prompt=summary_prompt,
            system_prompt=(
                "You write factual conversation summaries for an enterprise assistant. "
                "Output plain text only — no preamble."
            ),
            org_id=org_id,
        )
        new_summary = (result.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "conversation summarization failed org_id=%s error=%s",
            org_id,
            str(exc),
        )
        return PreparedConversationContext(messages=list(recent), summary=summary, summary_updated=False)

    if not new_summary:
        return PreparedConversationContext(messages=list(recent), summary=summary, summary_updated=False)

    trimmed = list(recent)
    while trimmed and total_tokens(trimmed) > threshold and len(trimmed) > 1:
        trimmed.pop(0)

    return PreparedConversationContext(
        messages=trimmed,
        summary=new_summary,
        summary_updated=new_summary != summary,
    )


def _message_contents(messages: list[dict[str, Any]]) -> list[str]:
    return [str(message.get("content") or "") for message in messages]


def load_conversation_summary(
    client: Any,
    *,
    conversation_id: str,
    org_id: str,
    user_id: str,
) -> str | None:
    try:
        response = (
            client.table("conversations")
            .select("last_summary")
            .eq("id", conversation_id)
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        value = response.data[0].get("last_summary")
        return str(value).strip() if value else None
    except Exception as exc:  # noqa: BLE001
        logger.debug("load_conversation_summary skipped conversation_id=%s error=%s", conversation_id, exc)
        return None


def persist_conversation_summary(
    client: Any,
    *,
    conversation_id: str,
    org_id: str,
    user_id: str,
    summary: str,
) -> None:
    try:
        client.table("conversations").update(
            {"last_summary": summary.strip()}
        ).eq("id", conversation_id).eq("org_id", org_id).eq("user_id", user_id).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "persist_conversation_summary failed conversation_id=%s error=%s",
            conversation_id,
            str(exc),
        )
