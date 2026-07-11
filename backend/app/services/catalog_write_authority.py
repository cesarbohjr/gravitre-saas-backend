"""Catalog-driven write/read authority for approval gating.

Single source of truth for “does this connector action mutate?” using ActionSpec
fields (kind, scopes, destructive, requires_approval) — not tool-name patterns.
"""
from __future__ import annotations

from typing import Iterable


def catalog_scopes_indicate_mutation(scopes: Iterable[str] | None) -> bool:
    """True when catalog OAuth/capability scopes declare a mutating capability.

    Catalog ``kind`` is overloaded (v3/v4 “advanced” tier often still mutates). Scopes
    such as ``hubspot:lists:write`` / ``apollo:tasks:write`` are the write/read signal.
    """
    for scope in scopes or ():
        text = str(scope or "").strip().lower()
        if not text or text.endswith(":*"):
            continue
        leaf = text.rsplit(":", 1)[-1]
        if leaf in {"read", "readonly", "analytics"} or leaf.endswith("_read"):
            continue
        if leaf in {
            "write",
            "enroll",
            "delete",
            "send",
            "post",
            "create",
            "update",
            "manage",
            "admin",
            "identify",
            "track",
            "group",
        }:
            return True
        if "write" in leaf or leaf.endswith("_write"):
            return True
    return False


def catalog_action_requires_write_approval(
    *,
    kind: str | None,
    destructive: bool = False,
    requires_approval: bool = False,
    scopes: Iterable[str] | None = None,
) -> bool:
    """Schema-driven write gate using catalog ActionSpec fields."""
    normalized = str(kind or "").strip().lower()
    if requires_approval or destructive or normalized == "write":
        return True
    if normalized == "read":
        return False
    # kind == "advanced" (or unknown): scopes are the write/read authority.
    return catalog_scopes_indicate_mutation(scopes)
