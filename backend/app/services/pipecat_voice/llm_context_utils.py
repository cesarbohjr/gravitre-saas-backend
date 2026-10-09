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
    last_role = ""
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
        if role and text:
            last_role = role
        if role in {"user", "assistant"} and text:
            messages.append({"role": role, "content": text})
    # Only a context that ends on a user message carries a turn to answer. One
    # that ends on the assistant, or on a developer/system note (Pipecat's
    # empty-turn recovery appends one), used to hand back the previous user
    # message, which the brain then answered a second time.
    if last_role == "user" and messages and messages[-1]["role"] == "user":
        return messages[-1]["content"], messages[:-1]
    history = messages[:-1] if messages and messages[-1]["role"] == "user" else messages
    return "", history


def _norm(text: str) -> str:
    import re

    return " ".join(re.sub(r"[^\w\s]", " ", (text or "").casefold()).split())


def _same_message(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if str(a.get("role") or "") != str(b.get("role") or ""):
        return False
    left, right = _norm(str(a.get("content") or "")), _norm(str(b.get("content") or ""))
    if not left or not right:
        return False
    if left == right:
        return True
    # A barge-in persists only the heard prefix of an assistant reply.
    return str(a.get("role") or "") == "assistant" and (left.startswith(right) or right.startswith(left))


def merge_durable_and_socket_history(
    durable: list[dict[str, Any]], socket_history: list[dict[str, Any]], *, limit: int = 48
) -> list[dict[str, Any]]:
    """One ordered history for a voice turn: durable rows, then unpersisted socket turns.

    ``durable`` is the pre-socket seed followed by rows persisted since (marked
    ``_live``: text typed while Talk is open and this socket's own completed
    voice turns). Socket turns that already appear among the live rows, in
    order, are not repeated; socket turns after the last one found (the
    in-flight or not-yet-persisted ones) are appended. Seed rows are never used
    for de-duplication, so a legitimately repeated utterance stays twice.
    """
    seed = [{k: v for k, v in dict(m).items() if k != "_live"} for m in durable if not m.get("_live")]
    live = [{k: v for k, v in dict(m).items() if k != "_live"} for m in durable if m.get("_live")]
    socket = [dict(m) for m in socket_history or []]
    if not live:
        return (seed + socket)[-limit:]
    pointer = 0
    last_matched = -1
    for idx, message in enumerate(socket):
        for j in range(pointer, len(live)):
            if _same_message(message, live[j]):
                pointer = j + 1
                last_matched = idx
                break
    return (seed + live + socket[last_matched + 1 :])[-limit:]
