"""Normalize user query text for clustering and analytics (v2)."""
from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s'-]", re.UNICODE)


def normalize_query(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation noise."""
    value = (text or "").strip().lower()
    if not value:
        return ""
    value = _PUNCT.sub(" ", value)
    value = _WHITESPACE.sub(" ", value).strip()
    return value[:2000]
