"""Plain-language closing lines for tool-backed chat answers.

A finished read should read like a person answered it: what came back, whether
anything is needed from the user, and what they can do next. Internal ids,
action keys and row counters belong in the Details view, never in the answer.
"""
from __future__ import annotations

_OBJECT_FOLLOW_UPS: tuple[tuple[str, str], ...] = (
    ("contact", "list them, or break them down by owner or lifecycle stage"),
    ("deal", "list the deals, or break the pipeline down by stage or owner"),
    ("compan", "list the companies, or break them down by industry or owner"),
    ("invoice", "list the invoices, or show which ones are overdue"),
    ("ticket", "list the tickets, or show which ones are still open"),
)


def read_next_steps(action_key: str | None, count: int | None) -> str:
    """One or two sentences saying nothing else is needed and what could come next."""
    key = str(action_key or "").lower()
    if count is not None and count <= 0:
        return (
            "If you expected results, try a broader search or check that the right "
            "account is connected."
        )
    for needle, follow_up in _OBJECT_FOLLOW_UPS:
        if needle in key:
            return f"Want me to {follow_up}?"
    return "Want me to list them or dig into any of them?"


def with_next_steps(answer: str, action_key: str | None, count: int | None) -> str:
    """Append next steps to a read answer unless it already closes with guidance."""
    text = str(answer or "").strip()
    if not text:
        return text
    lowered = text.lower()
    if "nothing else is needed" in lowered or "next step" in lowered or "want me to" in lowered:
        return text
    return f"{text}\n\n{read_next_steps(action_key, count)}"
