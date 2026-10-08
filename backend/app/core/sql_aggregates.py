"""Helpers for endpoints that aggregate in SQL via PostgREST RPC.

Page-load endpoints call a STABLE SQL function (``client.rpc``) so counting happens
in Postgres instead of pulling every row into Python. Because code can deploy before
the migration is applied, callers fall back to a Python path when the function is
missing; that fallback must page through every row so counts are not silently capped
at PostgREST's ``max_rows`` (1000 by default on Supabase).
"""
from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

# Supabase's default PostgREST max_rows. Pages shorter than this mean "last page".
DEFAULT_PAGE_SIZE = 1000
# Hard stop so a misbehaving backend can never loop forever (10M rows at 1000/page).
_MAX_PAGES = 10_000

_MISSING_FUNCTION_CODES = {"PGRST202", "42883"}

_fallback_logged: set[str] = set()
_fallback_lock = threading.Lock()


class UnexpectedRpcPayload(ValueError):
    """The RPC answered but not in the documented shape."""


def is_missing_function_error(exc: BaseException) -> bool:
    """True when PostgREST/Postgres reports the RPC function does not exist."""
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code.upper() in _MISSING_FUNCTION_CODES:
        return True
    message = str(exc)
    upper = message.upper()
    if any(c in upper for c in _MISSING_FUNCTION_CODES):
        return True
    lower = message.lower()
    return ("function" in lower and "does not exist" in lower) or "could not find the function" in lower


def log_fallback_once(function_name: str, reason: str) -> None:
    """Log (once per process per function) that the Python fallback is in use."""
    with _fallback_lock:
        if function_name in _fallback_logged:
            return
        _fallback_logged.add(function_name)
    logger.warning(
        "sql_aggregate_fallback function=%s reason=%s — using paged Python aggregation; "
        "apply migration 20261008020000_page_load_aggregates.sql",
        function_name,
        reason,
    )


def reset_fallback_log_state() -> None:
    """Test hook: forget which fallbacks were already logged."""
    with _fallback_lock:
        _fallback_logged.clear()


def rpc_object(client: Any, function_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Call an RPC that returns a single jsonb object and return it as a dict.

    Raises the underlying exception for missing-function and other errors, and
    ``UnexpectedRpcPayload`` when the answer is not a JSON object.
    """
    data = client.rpc(function_name, params).execute().data
    if isinstance(data, list) and len(data) == 1:
        data = data[0]
    if not isinstance(data, dict):
        raise UnexpectedRpcPayload(f"{function_name} returned {type(data).__name__}")
    return data


def fetch_all_rows(build_query: Any, *, page_size: int = DEFAULT_PAGE_SIZE) -> list[dict[str, Any]]:
    """Page through a PostgREST select with ``.range()`` until a short page.

    ``build_query`` is a zero-arg callable returning a fresh, ordered select builder
    (builders are mutable, so each page gets its own).
    """
    rows: list[dict[str, Any]] = []
    offset = 0
    for _ in range(_MAX_PAGES):
        batch = build_query().range(offset, offset + page_size - 1).execute().data
        if batch is None:
            batch = []
        if not isinstance(batch, list):
            raise TypeError(f"expected a list of rows from PostgREST, got {type(batch).__name__}")
        rows.extend(batch)
        if len(batch) < page_size:
            return rows
        offset += page_size
    logger.error("fetch_all_rows hit page limit pages=%s page_size=%s", _MAX_PAGES, page_size)
    return rows
