"""Phase F5 — provider prompt-prefix cache helpers.

OpenAI automatic prefix cache hits when the leading tokens stay byte-identical.
Anthropic needs an explicit ``cache_control`` breakpoint on the stable system
block. Application response-cache isolation for yes/no is unchanged
(``intent_gateway.response_cache_eligible``) — confirmations never share a
cached answer across conversations.
"""
from __future__ import annotations

from typing import Any

from app.services.intent_gateway import response_cache_eligible

# Headings that change per turn. Everything before the first of these can sit
# in the provider prompt-cache prefix.
_VOLATILE_HEADINGS = (
    "## Anti-repeat",
    "## Tone Adaptation",
    "## Conversation Task State",
    "## Operator Act Context",
    "## Your Internal Knowledge",
    "## Current Business Context",
    "## Learned Company Intelligence",
    "## Recent Task History",
    "## Incoming Briefing",
    "## Assembled Memory Context",
    "## Assembled Graph Context",
)


def confirmation_response_cache_isolated(question: str) -> bool:
    """True when this user text must not reuse a cross-turn canned answer."""
    return not response_cache_eligible(question)


def split_stable_prefix(system_prompt: str) -> tuple[str, str]:
    """Split a system prompt into (stable_prefix, volatile_tail)."""
    text = system_prompt or ""
    if not text.strip():
        return "", ""
    cut: int | None = None
    for heading in _VOLATILE_HEADINGS:
        idx = text.find(heading)
        if idx >= 0 and (cut is None or idx < cut):
            cut = idx
    if cut is None:
        return text.strip(), ""
    return text[:cut].strip(), text[cut:].strip()


def anthropic_cached_system(system_prompt: str) -> str | list[dict[str, Any]] | None:
    """Anthropic ``system`` value with a cache breakpoint on the stable prefix."""
    stable, volatile = split_stable_prefix(system_prompt)
    if not stable and not volatile:
        return None
    if not stable:
        return volatile
    blocks: list[dict[str, Any]] = [
        {"type": "text", "text": stable, "cache_control": {"type": "ephemeral"}},
    ]
    if volatile:
        blocks.append({"type": "text", "text": volatile})
    return blocks


def openai_system_messages(system_prompt: str) -> list[dict[str, str]]:
    """Two OpenAI system messages so the stable prefix can hit automatic cache.

    Consecutive identical leading tokens are what OpenAI prefix-caches. Splitting
    after the first volatile heading keeps persona/rules byte-stable across turns
    while RAG, task state, and operator-act JSON stay in the second message.
    """
    stable, volatile = split_stable_prefix(system_prompt)
    out: list[dict[str, str]] = []
    if stable:
        out.append({"role": "system", "content": stable})
    if volatile:
        out.append({"role": "system", "content": volatile})
    return out


def history_as_prefix_messages(
    history: list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    """Conversation turns as role/content messages (stable prefix after system)."""
    out: list[dict[str, str]] = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            out.append({"role": role, "content": content})
    return out
