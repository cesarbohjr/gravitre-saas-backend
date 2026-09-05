"""Shared LLMContext -> (user_text, history) extraction.

Factored out of cognitive_llm.py (2026-09-05) so the genuine speculative-
generation path (speculative_prefetch.py, triggered on partial/probable-EOT
text) and the confirmed-turn path (cognitive_llm.py, triggered at confirmed
end-of-turn) build history from the exact same accessor — required for a
speculative run's buffered output to be honestly reusable at confirmed EOT
(same prompt inputs modulo the query text itself, not a divergent build).
"""
from __future__ import annotations

from typing import Any


def messages_from_context(context: Any) -> tuple[str, list[dict[str, Any]]]:
    """Extract latest user text + prior history from a Pipecat LLMContext.

    `history` reflects only already-completed turns: the aggregator that
    owns `context` appends the current utterance's TranscriptionFrame only
    once the turn is confirmed, so calling this mid-utterance (from a partial
    transcript, before confirmation) correctly yields the same prior-turn
    history a confirmed call would use — the current utterance is not yet
    in `context` either way.
    """
    messages: list[dict[str, Any]] = []
    get_messages = getattr(context, "get_messages", None)
    raw = get_messages() if callable(get_messages) else getattr(context, "messages", None) or []
    for m in raw or []:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "").strip().lower()
        content = m.get("content")
        if isinstance(content, list):
            text_parts = [
                str(p.get("text") or "")
                for p in content
                if isinstance(p, dict) and p.get("type") in {None, "text", "input_text"}
            ]
            content = " ".join(t for t in text_parts if t).strip()
        text = str(content or "").strip()
        if role in {"user", "assistant"} and text:
            messages.append({"role": role, "content": text})
    user_text = ""
    for m in reversed(messages):
        if m["role"] == "user":
            user_text = m["content"]
            break
    history = messages[:-1] if messages and messages[-1]["role"] == "user" else messages
    return user_text, history
