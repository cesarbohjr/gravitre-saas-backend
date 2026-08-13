"""Temporal field aliases for Knowledge Fabric documents (Phase D item 3).

Proposal names: valid_from / valid_until / superseded_by
Existing columns: effective_at / superseded_at / (new) superseded_by
"""
from __future__ import annotations

from typing import Any


def resolve_temporal_fields(
    *,
    effective_at: str | None = None,
    superseded_at: str | None = None,
    valid_from: str | None = None,
    valid_until: str | None = None,
    superseded_by: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Normalize proposal aliases onto storage columns.

    Preference: explicit storage names, then aliases, then metadata aliases.
    """
    meta = metadata if isinstance(metadata, dict) else {}
    eff = effective_at or valid_from or meta.get("effective_at") or meta.get("valid_from")
    until = superseded_at or valid_until or meta.get("superseded_at") or meta.get("valid_until")
    by = superseded_by or meta.get("superseded_by")
    return {
        "effective_at": str(eff) if eff else None,
        "superseded_at": str(until) if until else None,
        "superseded_by": str(by) if by else None,
        # Proposal-facing aliases (same values; DB may also expose generated columns)
        "valid_from": str(eff) if eff else None,
        "valid_until": str(until) if until else None,
    }


def document_is_currently_valid(doc: dict[str, Any] | None, *, now_iso: str | None = None) -> bool:
    """True when the document has not been superseded (valid_until / superseded_at unset or future)."""
    if not isinstance(doc, dict):
        return True
    until = doc.get("valid_until") or doc.get("superseded_at")
    if not until:
        return True
    if not now_iso:
        from datetime import datetime, timezone

        now_iso = datetime.now(timezone.utc).isoformat()
    try:
        return str(until) > str(now_iso)
    except Exception:  # noqa: BLE001
        return True


def attach_temporal_aliases(doc: dict[str, Any] | None) -> dict[str, Any]:
    """Ensure a document dict exposes both storage and proposal field names."""
    if not isinstance(doc, dict):
        return {}
    resolved = resolve_temporal_fields(
        effective_at=doc.get("effective_at"),
        superseded_at=doc.get("superseded_at"),
        valid_from=doc.get("valid_from"),
        valid_until=doc.get("valid_until"),
        superseded_by=doc.get("superseded_by"),
        metadata=doc.get("metadata") if isinstance(doc.get("metadata"), dict) else None,
    )
    out = dict(doc)
    out.update({k: v for k, v in resolved.items() if v is not None or k not in out})
    return out
