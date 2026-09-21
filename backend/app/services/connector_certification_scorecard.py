"""Internal connector readiness scorecard (2.0-L).

Engineering vocabulary only. Never emit customer Certified / TRAINED / live
badges, prices, or Enable toggles.
"""
from __future__ import annotations

from typing import Any

from app.connectors.action_catalog.f1_read_slice import is_f1_read_action
from app.connectors.action_catalog.registry import get_action_spec
from app.services.tool_service import list_registered_actions

INTERNAL_LAYERS = (
    "registered",
    "configured",
    "connected",
    "authorized",
    "resource_ready",
    "action_ready",
    "capability_ready",
    "governance_ready",
    "test_verified",
    "production_verified",
)

FORBIDDEN_CUSTOMER_LABELS = ("certified", "trained", "live", "enable")

DEFAULT_VENDOR_ACTIONS: dict[str, str] = {
    "hubspot": "hubspot.deals.list",
    "google_analytics": "google_analytics.reports.run",
    "google_search_console": "google_search_console.searchAnalytics.query",
    "gmail": "gmail.messages.list",
    "quickbooks": "quickbooks.invoices.list",
    "zendesk": "zendesk.tickets.list",
    "salesforce": "salesforce.leads.search",
    "google_calendar": "google_calendar.events.list",
    "slack": "slack.conversations.list",
}


def _truthy(value: Any) -> bool:
    return bool(value) and str(value).strip().lower() not in {"false", "0", "none", "null"}


def classify_connector_action(
    *,
    action_key: str,
    availability: dict[str, Any] | None = None,
    production_verified: bool = False,
    test_verified: bool | None = None,
    implemented: bool | None = None,
) -> dict[str, Any]:
    spec = get_action_spec(action_key)
    registered = spec is not None
    avail = availability if isinstance(availability, dict) else {}
    configured = _truthy(avail.get("configured")) if avail else registered
    connected = _truthy(avail.get("connected") or avail.get("execution_available"))
    authorized = _truthy(avail.get("authenticated") and avail.get("token_valid") and avail.get("scopes_valid", True))
    resource_ready = connected and authorized and (
        not spec or not spec.resource_requirements or _truthy(avail.get("resource_ready", True))
    )
    implemented_flag = (
        bool(implemented)
        if implemented is not None
        else (action_key in set(list_registered_actions()) if action_key else False)
    )
    action_ready = bool(
        registered
        and implemented_flag
        and spec
        and spec.execution_adapter
        and spec.parameter_source_rules
        and (spec.kind != "read" or is_f1_read_action(action_key) or spec.governance_classification)
    )
    capability_ready = bool(spec and spec.capabilities)
    governance_ready = bool(spec and spec.governance_classification in {"read", "write"})
    tests_ok = bool(test_verified) if test_verified is not None else bool(action_ready and registered)
    layers = {
        "registered": registered,
        "configured": configured,
        "connected": connected,
        "authorized": authorized,
        "resource_ready": resource_ready,
        "action_ready": action_ready,
        "capability_ready": capability_ready,
        "governance_ready": governance_ready,
        "test_verified": tests_ok,
        "production_verified": bool(production_verified and tests_ok and action_ready and authorized),
    }
    current = "unregistered"
    for name in INTERNAL_LAYERS:
        if layers[name]:
            current = name
        else:
            break
    return {
        "action_key": action_key,
        "track": "internal_scorecard",
        "customer_badge": None,
        "layers": layers,
        "current_internal_state": current,
        "connected_does_not_mean_action_ready": connected and not action_ready,
    }


def attach_internal_readiness(row: dict[str, Any], *, action_key: str | None = None) -> dict[str, Any]:
    """Stamp engineering scorecard onto an availability row. Never a customer badge."""
    vendor = str(row.get("vendor") or row.get("type") or "").strip().lower()
    key = str(action_key or "").strip() or DEFAULT_VENDOR_ACTIONS.get(vendor)
    if not key:
        return row
    try:
        row["internal_readiness"] = classify_connector_action(action_key=key, availability=row)
    except Exception:
        row.setdefault("internal_readiness", None)
    return row


def scorecard_from_availability_rows(
    rows: list[dict[str, Any]],
    *,
    action_keys: list[str],
    production_verified_keys: frozenset[str] | None = None,
) -> dict[str, Any]:
    proven = production_verified_keys or frozenset()
    by_vendor = {str(row.get("vendor") or row.get("type") or "").lower(): row for row in rows}
    items = []
    for key in action_keys:
        vendor = key.split(".", 1)[0]
        items.append(
            classify_connector_action(
                action_key=key,
                availability=by_vendor.get(vendor),
                production_verified=key in proven,
            )
        )
    return {
        "scorecard": "internal_connector_readiness",
        "customer_facing_certification": False,
        "items": items,
    }
