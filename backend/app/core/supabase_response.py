"""Helpers for supabase-py execute() responses (v1 vs v2)."""
from __future__ import annotations

from typing import Any


def response_error(response: Any) -> Any | None:
    """Return a PostgREST error if present.

    supabase-py v1 attached failures to `.error`. v2 raises AttributeError when
    callers read that attribute — use this helper everywhere instead.
    """
    return getattr(response, "error", None)
