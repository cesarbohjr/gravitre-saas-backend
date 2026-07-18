"""Governance-bound internet research query construction.

Per closed governance review: only the user's search query is sent externally —
not conversation context, RAG blocks, or follow-up expansion. Max 2000 chars.

All internet research entry points must call ``prepare_internet_research_query``
before any vendor API call.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

GOVERNANCE_MAX_QUERY_CHARS = 2000

_CONTEXT_BLOCK_RE = re.compile(
    r"<(?:knowledge_base|internet_research|intelligence_pack|conversation|memory|context)[^>]*>.*?</[^>]+>",
    re.DOTALL | re.IGNORECASE,
)
_STANDALONE_TAG_RE = re.compile(
    r"</?(?:knowledge_base|internet_research|intelligence_pack|conversation|memory|context)[^>]*>",
    re.IGNORECASE,
)
_EXPLICIT_QUERY_RE = re.compile(r"(?:^|\n)\s*(?:search\s+)?query\s*:\s*(.+)$", re.IGNORECASE | re.DOTALL)
_USER_TURN_RE = re.compile(r"(?:^|\n)\s*user\s*:\s*(.+?)(?=\n\s*(?:assistant|system|ai|human)\s*:|$)", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class PreparedInternetResearchQuery:
    """Sanitized query ready for external grounding/search APIs."""

    query: str
    original_length: int
    sanitized_length: int
    was_truncated: bool
    context_stripped: bool

    def to_metadata(self) -> dict[str, Any]:
        return {
            "query_sent": self.query,
            "original_length": self.original_length,
            "sanitized_length": self.sanitized_length,
            "was_truncated": self.was_truncated,
            "context_stripped": self.context_stripped,
            "governance_max_chars": GOVERNANCE_MAX_QUERY_CHARS,
        }


def _strip_context_blocks(text: str) -> tuple[str, bool]:
    if not text:
        return "", False
    stripped = _CONTEXT_BLOCK_RE.sub(" ", text)
    stripped = _STANDALONE_TAG_RE.sub(" ", stripped)
    return stripped, stripped != text


def _extract_bare_query(text: str) -> tuple[str, bool]:
    """Prefer explicit Query: lines, then last User: turn, else cleaned free text."""
    explicit = _EXPLICIT_QUERY_RE.search(text)
    if explicit:
        return explicit.group(1).strip(), True

    user_turns = [match.group(1).strip() for match in _USER_TURN_RE.finditer(text)]
    if user_turns:
        return user_turns[-1], True

    # Collapse accidental multi-turn blobs without markers to the final paragraph.
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    if len(paragraphs) > 1:
        return paragraphs[-1], True

    return text.strip(), False


def prepare_internet_research_query(raw: str | None) -> PreparedInternetResearchQuery:
    """Build the vendor-facing search string at the single governance chokepoint."""
    original = str(raw or "")
    without_blocks, blocks_stripped = _strip_context_blocks(original)
    bare, turns_stripped = _extract_bare_query(without_blocks)
    cleaned = " ".join(bare.split())
    was_truncated = len(cleaned) > GOVERNANCE_MAX_QUERY_CHARS
    governed = cleaned[:GOVERNANCE_MAX_QUERY_CHARS]

    return PreparedInternetResearchQuery(
        query=governed,
        original_length=len(original),
        sanitized_length=len(governed),
        was_truncated=was_truncated,
        context_stripped=blocks_stripped or turns_stripped,
    )
