"""Routing view of a request. Constraints remain in the original tool prompt.

Negative clauses and requests for trace/approval presentation are not executable
steps. This helper selects candidates only; it never authorizes an action.
"""
from __future__ import annotations

import re

_CLAUSE = re.compile(r"(?<=[.!?;])\s+|\s+(?:but|however)\s+", re.I)
_NEGATIVE = re.compile(r"\b(?:do\s+not|don['’]?t|never|must\s+not|without)\s+|(?:^|,\s*)no\s+(?!later\b|more\s+than\b|less\s+than\b)", re.I)
_QUOTED = re.compile(r'"[^"\n]*"|“[^”\n]*”|‘[^’\n]*’|`[^`\n]*`|(?<!\w)\x27[^\x27\n]*\x27(?!\w)')
_META = re.compile(
    r"^(?:first\s+)?(?:show|report|preserve|include|return|provide|list)\b"
    r".*\b(?:approval|trace\s+marker|(?:recommendation|approval|workflow\s+run)\s+ids?)\b",
    re.I,
)


def actionable_clauses(message: str) -> list[str]:
    quoted: list[str] = []

    def protect(match: re.Match[str]) -> str:
        quoted.append(match.group())
        return f"\x00quoted{len(quoted) - 1}\x00"

    protected = _QUOTED.sub(protect, message or "")
    clauses: list[str] = []
    for clause in _CLAUSE.split(protected):
        # A trailing constraint can share a sentence with the positive request.
        # Keep only its positive prefix for routing, never the prohibited verb.
        clause = _NEGATIVE.split(clause, maxsplit=1)[0].strip(" ,.;")
        if clause and not _META.search(clause):
            for index, literal in enumerate(quoted):
                clause = clause.replace(f"\x00quoted{index}\x00", literal)
            clauses.append(clause)
    return clauses


def action_intent_text(message: str) -> str:
    # Literal message bodies and names are parameters, not connector requests.
    return _QUOTED.sub(" ", ". ".join(actionable_clauses(message)))


def is_native_work_request(message: str) -> bool:
    """Explicit Gravitre work must never be fulfilled with a connected app fallback."""
    text = action_intent_text(message)
    return bool(re.search(
        r"\b(?:internal\s+gravitre|gravitre(?:['’]s)?\s+(?:assignment|workflow|play|agent)|"
        r"(?:assignment|workflow|play|agent)\b[^.!?;]{0,80}\b(?:in|within)\s+gravitre)\b",
        text, re.I,
    ))
