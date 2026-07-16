"""Normalize chat user text before connector planning / execution."""
from __future__ import annotations

import re

# Injected in assistant chat for LLM context — must never become tool args.
_SCOPE_PREFIX = re.compile(
    r"^\[(?:Department context:\s*[^\]]+|Cross-department cowork[^\]]*)\]\s*",
    re.IGNORECASE,
)


def strip_assistant_scope_prefix(text: str | None) -> str:
    """Remove department / cross-department banners from user task text."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    return _SCOPE_PREFIX.sub("", cleaned).strip()
