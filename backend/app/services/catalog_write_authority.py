"""Catalog-driven write/read authority for approval gating.

Single source of truth for “does this connector action mutate?” using ActionSpec
fields (kind, scopes, destructive, requires_approval) — not tool-name patterns.

Surfaces (chat/ReAct, canvas execute) MUST call into this module rather than
re-deriving write/read classification independently.
"""
from __future__ import annotations

from typing import Any, Iterable

from app.services.event_intelligence_service import WRITE_ACTION_SUFFIXES

# Extra write verbs not covered by EventIntelligence WRITE_ACTION_SUFFIXES.
# Last-resort only when a registry/catalog row is missing.
_EXTRA_WRITE_SUFFIXES = (
    ".send",
    ".post_message",
    ".post",
    ".add",
    ".remove",
    ".subscribe",
    ".trigger",
    ".assign",
    ".transition",
    ".comment",
    ".acknowledge",
    ".resolve",
    ".reassign",
    ".escalate",
    ".add_note",
    ".update_stage",
    ".add_contact",
    ".add_project",
    ".add_member",
    ".add_contacts",
)


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


def matrix_entry_requires_write_approval(entry: Any) -> bool:
    """Apply catalog_action_requires_write_approval to a matrix / ActionSpec-like row."""
    scopes = getattr(entry, "required_scopes", None)
    if scopes is None:
        scopes = getattr(entry, "scopes", None)
    return catalog_action_requires_write_approval(
        kind=getattr(entry, "kind", None),
        destructive=bool(getattr(entry, "destructive", False)),
        requires_approval=bool(getattr(entry, "requires_approval", False)),
        scopes=scopes,
    )


def action_name_indicates_write(action: str) -> bool:
    """Last-resort suffix heuristic when no catalog row exists."""
    lowered = str(action or "").strip().lower()
    if not lowered:
        return False
    if any(lowered.endswith(suffix) for suffix in WRITE_ACTION_SUFFIXES):
        return True
    return any(lowered.endswith(suffix) for suffix in _EXTRA_WRITE_SUFFIXES)


def find_matrix_entry_for_invoke_action(action: str) -> Any | None:
    """Resolve an invoke_tool action key to a connector execution matrix entry."""
    lowered = str(action or "").strip().lower()
    if not lowered:
        return None
    try:
        from app.services.connector_execution_matrix import build_connector_execution_matrix

        for entry in build_connector_execution_matrix():
            keys = {
                str(getattr(entry, "registry_key", "") or "").strip().lower(),
                str(getattr(entry, "action_key", "") or "").strip().lower(),
            }
            if lowered in keys:
                return entry
    except Exception:  # noqa: BLE001
        return None
    return None


def find_matrix_entry_for_tool_registry_key(tool_registry_key: str) -> Any | None:
    """Resolve a ReAct tool registry key to a connector execution matrix entry."""
    name = str(tool_registry_key or "").strip()
    if not name:
        return None
    try:
        from app.services.connector_execution_matrix import build_connector_execution_matrix

        for entry in build_connector_execution_matrix():
            if str(getattr(entry, "tool_registry_key", "") or "") == name:
                return entry
    except Exception:  # noqa: BLE001
        return None
    return None


def invoke_action_requires_write_approval(action: str) -> bool:
    """Shared write classification for an invoke_tool / connector action key.

    1) Catalog matrix row → ``catalog_action_requires_write_approval``
    2) Else suffix fallback (same last-resort used by chat/ReAct)
    """
    entry = find_matrix_entry_for_invoke_action(action)
    if entry is not None:
        return matrix_entry_requires_write_approval(entry)
    return action_name_indicates_write(action)


def mcp_hints_from_schema(schema: dict[str, Any] | None) -> tuple[bool | None, bool | None]:
    """Extract MCP standard readOnlyHint / destructiveHint from tool input schema."""
    if not isinstance(schema, dict):
        return None, None
    ann = schema.get("annotations")
    if not isinstance(ann, dict):
        ann = {}
    read_only = ann.get("readOnlyHint")
    if read_only is None and "readOnlyHint" in schema:
        read_only = schema.get("readOnlyHint")
    destructive = ann.get("destructiveHint")
    if destructive is None and "destructiveHint" in schema:
        destructive = schema.get("destructiveHint")
    ro = bool(read_only) if read_only is not None else None
    de = bool(destructive) if destructive is not None else None
    return ro, de


def mcp_tool_requires_write_approval(
    *,
    capability_tier: str | None = None,
    requires_approval: bool | None = None,
    read_only_hint: bool | None = None,
    destructive_hint: bool | None = None,
) -> bool:
    """Annotation-driven MCP write gate — same authority model as native catalog."""
    if read_only_hint is True:
        return False
    if requires_approval is True or destructive_hint is True:
        return True
    if str(capability_tier or "").strip().lower() == "write":
        return True
    return False
