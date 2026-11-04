"""Repair generic clarification boilerplate without weakening factual checks."""
from __future__ import annotations

import re
from typing import Any


_GENERIC = re.compile(
    r"(?i)(?:I may be missing context\s*[—–-]\s*)?(?:could you|can you) clarify"
    r"(?: what you need)?(?: or point me to a specific (?:record or document|document or record))?\?\s*$"
)
_UNVERIFIED = "I found related information, but not enough reliable context to answer confidently."


def repair_generic_clarification(answer: str, *, query: str, history: list[dict[str, Any]] | None, needs_clarification: bool) -> str:
    text = (answer or "").strip()
    generic = _GENERIC.search(text)
    if generic is None and (text or not needs_clarification):
        return text
    substantive = text[:generic.start()].strip() if generic else ""
    if substantive and substantive != _UNVERIFIED:
        # Keep useful content and any specific question already authored.
        return substantive
    if re.search(r"(?i)\b(?:connectors?|integrations?|e-?mail\s+(?:providers?|services?|connectors?|integrations?)|outlook\s+connector)\b", query):
        # A clearly stated inventory request cannot be clarified into a new task.
        # A failed live lookup is missing evidence, not missing user context.
        return ("I couldn\'t verify your connected email services right now. "
                "Please retry the connector-status check; I can\'t confirm which providers are available until it succeeds.")
    if re.search(r"(?i)\b(e-?mails?|gmail|outlook|connectors?)\b", query):
        question = "Are you asking about connected email services or individual messages?"
    elif re.search(r"(?i)\b(records?|contacts?|deals?|accounts?|invoices?)\b", query):
        question = "Which account or record should I check?"
    else:
        question = "What result are you trying to get?"
    last = next((row.get("content", "") for row in reversed(history or []) if isinstance(row, dict) and row.get("role") == "assistant"), "")
    if isinstance(last, str) and question in last:
        return "I still can't verify that request. Try naming the service or record and the action you want."
    return f"I couldn't verify enough reliable information for that request. {question}"
