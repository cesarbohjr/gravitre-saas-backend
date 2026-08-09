"""Catalog-backed Diff/Undo answers — never a parallel hardcoded product list.

Phase 0/2: compensating counterparts live on ActionSpec.compensating_action.
Legacy compensation_service maps are imported once as seed for catalog lookup
until every vendor definition carries the field explicitly.
"""
from __future__ import annotations

from typing import Any

# Seed pairs promoted into ActionSpec lookups. Source of truth for *queries*
# is get_compensating_action(); this map is only used when ActionSpec lacks
# the field (migration window). New vendors must set ActionSpec.compensating_action.
_SEED_COMPENSATING_ACTIONS: dict[str, str] = {
    "hubspot.contacts.create": "hubspot.contacts.delete",
    "hubspot.contacts.update": "hubspot.contacts.update",  # restore via snapshot
    "hubspot.deals.create": "hubspot.deals.delete",
    "hubspot.deals.update": "hubspot.deals.update",
    "hubspot.deals.update_stage": "hubspot.deals.update_stage",
    "hubspot.notes.create": "hubspot.notes.delete",
    "zendesk.tickets.create": "zendesk.tickets.close",
    "zendesk.tickets.update": "zendesk.tickets.update",
}

_SEED_DIFF_ACTIONS: frozenset[str] = frozenset(
    {
        "hubspot.contacts.update",
        "hubspot.deals.update",
        "hubspot.deals.update_stage",
        "zendesk.tickets.update",
    }
)


def get_action_spec(invoke_action: str) -> Any | None:
    action = str(invoke_action or "").strip()
    if not action or "." not in action:
        return None
    vendor = action.split(".", 1)[0]
    try:
        from app.connectors.action_catalog.registry import get_vendor_spec

        vendor_spec = get_vendor_spec(vendor)
    except Exception:  # noqa: BLE001
        return None
    if vendor_spec is None:
        return None
    for spec in list(getattr(vendor_spec, "actions", ()) or ()):
        sid = str(getattr(spec, "id", "") or "")
        if sid == action or sid.endswith(action.split(".", 1)[-1]):
            return spec
        tool = str(getattr(spec, "tool", "") or "")
        if tool == action:
            return spec
    return None


def get_compensating_action(invoke_action: str) -> str | None:
    """Return catalog compensating action id, or None if irreversible / unknown."""
    action = str(invoke_action or "").strip()
    if not action:
        return None
    spec = get_action_spec(action)
    if spec is not None:
        catalog_value = getattr(spec, "compensating_action", None)
        if catalog_value is not None:
            value = str(catalog_value).strip()
            return value or None
    return _SEED_COMPENSATING_ACTIONS.get(action)


def supports_vendor_diff(invoke_action: str) -> bool:
    """True only when a real prior-value snapshot path exists for this action."""
    action = str(invoke_action or "").strip()
    if not action:
        return False
    spec = get_action_spec(action)
    if spec is not None and hasattr(spec, "supports_diff"):
        flagged = getattr(spec, "supports_diff")
        if flagged is not None:
            return bool(flagged)
    return action in _SEED_DIFF_ACTIONS


def undo_availability(invoke_action: str) -> dict[str, Any]:
    """Honest undo envelope for BusinessOutcome.undo section."""
    compensating = get_compensating_action(invoke_action)
    if compensating:
        return {
            "available": True,
            "compensating_action": compensating,
            "honest_unavailable_reason": None,
        }
    return {
        "available": False,
        "compensating_action": None,
        "honest_unavailable_reason": (
            "No catalog compensating action exists for this write. "
            "Undo is not available — the vendor change cannot be reversed through Gravitre."
        ),
    }
