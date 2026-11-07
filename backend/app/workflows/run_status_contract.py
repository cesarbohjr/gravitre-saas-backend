"""PR605: versioned, lossless workflow-to-run status contract.

v1 was a coarse projection, potentially conflating partial work with completed
and dropping review-required outcomes. v2 requires the contract-table migration
in this PR before application-side mirror writes are deployed.

Approvals are a request for permission, not execution success. Unknown
statuses must fail explicitly rather than become 'queued' or 'completed'.
"""
from __future__ import annotations

from typing import Final

RUN_STATUS_CONTRACT_VERSION: Final[int] = 2

# Keep in sync with the SQL mirror CASE in
# supabase/migrations/20261105090000_run_status_contract_v2.sql
_STATUS_MAP: Final[dict[str, str]] = {
    "pending": "queued",
    "queued": "queued",
    "running": "running",
    "verifying": "running",
    "completed": "completed",
    "success": "completed",
    "partial_success": "partial_success",
    "flagged_for_review": "flagged_for_review",
    "failed": "failed",
    "error": "failed",
    "verification_inconclusive": "failed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "pending_approval": "needs_approval",
    "awaiting_approval": "needs_approval",
    "needs_approval": "needs_approval",
    "paused": "paused",
}

CONTRACT_ALLOWED_STATUSES: Final[frozenset[str]] = frozenset(_STATUS_MAP.values())


def contract_run_status_v2(value: str | None) -> str:
    """Map a source status to the v2 contract without hiding unknown states."""
    normalized = str(value or "").strip().lower()
    if not normalized:
        raise ValueError("run status must be explicit")
    try:
        return _STATUS_MAP[normalized]
    except KeyError as exc:
        raise ValueError(f"unsupported source run status: {normalized}") from exc


def run_status_metadata(*, lifecycle: str, origin: str) -> dict[str, object]:
    normalized = str(lifecycle or "").strip().lower()
    contract_run_status_v2(normalized)
    return {
        "status_contract_version": RUN_STATUS_CONTRACT_VERSION,
        "execution_lifecycle": normalized,
        "mirrored_by": origin,
    }
