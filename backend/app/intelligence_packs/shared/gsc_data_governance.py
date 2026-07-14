"""GSC data-governance stop-line — raw query strings vs Memory/KG.

STA-312 pattern applied preemptively for Marketing (#6):
- Aggregate/rollup metrics (clicks, impressions, position by URL/page) may flow
  through the pack signal pipeline normally.
- Raw search query strings (searchAnalytics.query row-level query text) must NOT
  be written to Organizational Memory or the Knowledge Graph without Cesar
  governance sign-off.
"""
from __future__ import annotations

from typing import Any

# Locked 2026-07-14 — flip only after Cesar governance clear (same bar as Crunchbase/PDL).
GSC_RAW_QUERY_MEMORY_KG_ALLOWED = False


class GscGovernanceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "GSC_RAW_QUERY_MEMORY_KG_BLOCKED") -> None:
        super().__init__(message)
        self.code = code


def dimensions_include_query(dimensions: list[str] | tuple[str, ...] | None) -> bool:
    return any(str(d or "").strip().lower() == "query" for d in (dimensions or []))


def payload_contains_gsc_raw_queries(payload: Any) -> bool:
    """True when a GSC searchAnalytics-shaped payload includes query text."""
    if not isinstance(payload, dict):
        return False
    dims = payload.get("dimensions")
    if dimensions_include_query(dims if isinstance(dims, list) else None):
        return True
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return False
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("query") not in (None, ""):
            return True
        keys = row.get("keys")
        # Ambiguous without dimensions — treat non-empty keys + query dim flag only
        if isinstance(keys, list) and payload.get("includes_raw_queries") is True:
            return True
    return bool(payload.get("includes_raw_queries"))


def assert_gsc_safe_for_memory_kg(payload: Any, *, source: str = "google_search_console") -> None:
    """Raise when raw GSC query strings would be persisted to Memory/KG."""
    if GSC_RAW_QUERY_MEMORY_KG_ALLOWED:
        return
    if payload_contains_gsc_raw_queries(payload):
        raise GscGovernanceError(
            f"{source}: raw Search Console query strings cannot be written to "
            "Organizational Memory or Knowledge Graph without governance sign-off "
            "(STA-312 pattern). Use page/URL aggregates instead.",
        )


def sanitize_gsc_payload_for_memory_kg(payload: Any) -> dict[str, Any]:
    """Return a Memory/KG-safe copy: drop query dimension rows; keep page aggregates.

    Does not mutate the input. Raises if nothing safe remains and raw queries were present
    only when caller still tries to persist — prefer assert + aggregates path.
    """
    if not isinstance(payload, dict):
        return {}
    out = dict(payload)
    dims = [str(d) for d in (out.get("dimensions") or [])]
    if not dimensions_include_query(dims):
        out["memoryKgEligible"] = True
        out["includes_raw_queries"] = False
        return out

    safe_dims = [d for d in dims if d.lower() != "query"]
    rows_in = out.get("rows") if isinstance(out.get("rows"), list) else []
    safe_rows: list[dict[str, Any]] = []
    for row in rows_in:
        if not isinstance(row, dict):
            continue
        cleaned = {k: v for k, v in row.items() if str(k).lower() != "query"}
        if "query" in row or (isinstance(row.get("keys"), list) and "query" in [d.lower() for d in dims]):
            # Drop rows that only existed to carry query text when query was the sole dim
            if safe_dims:
                # Rebuild keys without query index if present
                if isinstance(cleaned.get("keys"), list) and dims:
                    q_idx = next((i for i, d in enumerate(dims) if d.lower() == "query"), None)
                    if q_idx is not None:
                        keys = list(cleaned["keys"])
                        if 0 <= q_idx < len(keys):
                            keys.pop(q_idx)
                        cleaned["keys"] = keys
                safe_rows.append(cleaned)
            continue
        safe_rows.append(cleaned)

    out["dimensions"] = safe_dims or ["page"]
    out["rows"] = safe_rows
    out["includes_raw_queries"] = False
    out["memoryKgEligible"] = True
    out["rawQueriesStripped"] = True
    return out


def annotate_gsc_tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Mark tool results for governance consumers (workflow cache OK; Memory/KG gated)."""
    out = dict(payload)
    has_queries = payload_contains_gsc_raw_queries(out)
    out["includes_raw_queries"] = has_queries
    out["memoryKgEligible"] = (not has_queries) and GSC_RAW_QUERY_MEMORY_KG_ALLOWED is False and not has_queries
    # Eligible when no raw queries (aggregates always OK)
    out["memoryKgEligible"] = not has_queries
    out["governanceNote"] = (
        "Raw GSC query strings are blocked from Organizational Memory/KG without governance sign-off. "
        "Page/URL aggregates may flow through the pack signal pipeline."
        if has_queries
        else "GSC aggregate/rollup metrics are Memory/KG eligible under normal pack ingestion."
    )
    return out
