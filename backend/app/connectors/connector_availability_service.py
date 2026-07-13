"""Canonical connector availability, health, and execution readiness."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.connectors.connection_health import (
    map_auth_status_to_connector_status,
    resolve_connector_auth_status,
    resolve_display_connector_status,
)
from app.connectors.hubspot_oauth import (
    load_oauth_tokens,
    normalize_vendor as normalize_hubspot_vendor,
)
from app.connectors.repository import list_connectors
from app.services.tool_service import list_registered_actions

SOURCE_OF_TRUTH = "connector_availability_service"

HUBSPOT_ACTION_REQUIRED_SCOPES: dict[str, tuple[str, ...]] = {
    "hubspot.contacts.search": ("crm.objects.contacts.read",),
    "hubspot.contacts.get": ("crm.objects.contacts.read",),
    "hubspot.contacts.create": ("crm.objects.contacts.write",),
    "hubspot.contacts.update": ("crm.objects.contacts.write",),
    "hubspot.deals.get": ("crm.objects.deals.read",),
    "hubspot.deals.create": ("crm.objects.deals.write",),
    "hubspot.deals.update": ("crm.objects.deals.write",),
}

WRITE_ACTION_HINTS = (".create", ".update", ".delete", ".write", ".post", ".send", ".enroll")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_vendor(vendor: str) -> str:
    return str(vendor or "").strip().lower().replace(" ", "").replace("-", "")


def _hubspot_oauth_configured(settings: Settings, environment_name: str | None) -> bool:
    from app.connectors.hubspot_oauth import hubspot_oauth_configured

    return hubspot_oauth_configured(settings, environment_name)


def _hubspot_scopes_valid(tokens: dict[str, Any] | None, action_key: str | None) -> tuple[bool, str | None]:
    if not tokens:
        return False, "missing_scope"
    scopes = {str(scope) for scope in (tokens.get("scopes") or [])}
    if not scopes:
        return True, None
    # Connected-integration listing (no action_key) must not require the full
    # authorize-time scope set. Smoke / partial grants (contacts+deals+lists
    # without companies/tickets/notes) are still a connected HubSpot connector;
    # per-action gates apply when action_key is set.
    if not action_key:
        return True, None
    required = HUBSPOT_ACTION_REQUIRED_SCOPES.get(action_key, ())
    if not required:
        return True, None
    missing = [scope for scope in required if scope not in scopes]
    if missing:
        return False, "missing_scope"
    return True, None


def _blocking_details(
    *,
    vendor: str,
    configured: bool,
    authenticated: bool,
    token_valid: bool,
    scopes_valid: bool,
    auth_status: str | None,
    action_key: str | None,
    action_registered: bool,
) -> tuple[str | None, str | None]:
    if not configured:
        return "misconfigured", f"Configure {vendor} OAuth in server settings or complete connector setup."
    if auth_status == "pending_auth":
        return "pending_auth", f"Complete OAuth for {vendor} on the Connectors page."
    if auth_status == "auth_expired" or not token_valid:
        return "token_expired", f"{vendor.title()} is configured, but authentication has expired. Reconnect {vendor.title()}."
    if not authenticated:
        return "pending_auth", f"Complete OAuth for {vendor} on the Connectors page."
    if not scopes_valid:
        return "missing_scope", (
            f"{vendor.title()} is connected, but required OAuth scopes are missing. "
            f"Reconnect {vendor.title()} and approve contact access."
        )
    if action_key and not action_registered:
        return "unsupported_action", (
            f"{vendor.title()} is connected, but {action_key} is not executable because the action is not registered."
        )
    return None, None


def evaluate_connector_availability(
    client: Any,
    org_id: str,
    row: dict[str, Any],
    settings: Settings,
    *,
    environment_name: str = "production",
    force_live: bool = False,
    action_key: str | None = None,
) -> dict[str, Any]:
    connector_id = str(row.get("id") or "")
    vendor = str(row.get("vendor") or row.get("type") or "")
    normalized_vendor = _normalize_vendor(vendor)
    env = str(row.get("environment") or environment_name)
    raw_status = str(row.get("status") or "disconnected")

    auth_status = resolve_connector_auth_status(
        client,
        org_id,
        connector_id,
        vendor,
        settings,
        environment_name=env,
        validate_remote=force_live,
    )
    mapped_status = map_auth_status_to_connector_status(auth_status, raw_status)
    display_status = resolve_display_connector_status(mapped_status, auth_status)

    configured = True
    authenticated = auth_status == "connected"
    token_valid = auth_status == "connected"
    scopes_valid = True

    # Phase 3: gravitree_managed uses platform credentials (no tenant OAuth)
    from app.intelligence_packs.shared.auth_mode import AuthMode, get_auth_mode, resolve_credential_source
    from app.services.gravitree_connector_activation import _platform_env_present

    if get_auth_mode(vendor) == AuthMode.GRAVITREE_MANAGED:
        present = _platform_env_present(vendor, settings)
        resolved = resolve_credential_source(
            vendor,
            org_has_secret=False,
            platform_env_present=present,
            settings=settings,
        )
        configured = True
        if resolved.get("ok") and raw_status in {"active", "connected", "healthy", "syncing"}:
            authenticated = True
            token_valid = True
            auth_status = "connected"
            mapped_status = map_auth_status_to_connector_status(auth_status, raw_status)
            display_status = resolve_display_connector_status(mapped_status, auth_status)
        elif resolved.get("ok") and raw_status in {"needs_connection", "pending_auth", "pending"}:
            authenticated = False
            token_valid = False
            auth_status = "pending_auth"
            mapped_status = "needs_connection"
            display_status = "disconnected"
            blocking_reason = "pending_auth"
            recovery_action = f"Activate {vendor} (Gravitree-managed) — no customer credentials required."
            action_registered = True
            if action_key:
                action_registered = action_key in set(list_registered_actions())
            return {
                "connector_id": connector_id,
                "vendor": vendor,
                "configured": configured,
                "authenticated": False,
                "token_valid": False,
                "scopes_valid": True,
                "health_status": mapped_status,
                "execution_available": False,
                "read_available": False,
                "write_available": False,
                "last_checked_at": _utc_now(),
                "source_of_truth": SOURCE_OF_TRUTH,
                "blocking_reason": blocking_reason,
                "recovery_action": recovery_action,
                "auth_status": auth_status,
                "display_status": display_status,
                "status": display_status,
                "connected": False,
                "raw_status": raw_status,
                "environment": env,
                "name": str(row.get("name") or vendor or "connector"),
                "auth_mode": AuthMode.GRAVITREE_MANAGED.value,
            }
        else:
            authenticated = False
            token_valid = False
            auth_status = "misconfigured"
            mapped_status = "error"
            display_status = "error"

    if normalize_hubspot_vendor(vendor) == "hubspot":
        configured = _hubspot_oauth_configured(settings, env)
        tokens = load_oauth_tokens(client, connector_id, settings) if configured else None
        if configured and not tokens:
            authenticated = False
            token_valid = False
        if auth_status != "connected":
            token_valid = False
        if token_valid:
            scopes_valid, _ = _hubspot_scopes_valid(tokens, action_key)

    action_registered = True
    if action_key:
        action_registered = action_key in set(list_registered_actions())

    blocking_reason, recovery_action = _blocking_details(
        vendor=vendor,
        configured=configured,
        authenticated=authenticated,
        token_valid=token_valid,
        scopes_valid=scopes_valid,
        auth_status=auth_status,
        action_key=action_key,
        action_registered=action_registered,
    )

    execution_available = blocking_reason is None and display_status in {"connected", "syncing"}
    read_available = execution_available
    write_available = execution_available
    if action_key and execution_available:
        if any(hint in action_key for hint in WRITE_ACTION_HINTS):
            read_available = False
        else:
            write_available = False

    return {
        "connector_id": connector_id,
        "vendor": vendor,
        "configured": configured,
        "authenticated": authenticated,
        "token_valid": token_valid,
        "scopes_valid": scopes_valid,
        "health_status": mapped_status,
        "execution_available": execution_available,
        "read_available": read_available,
        "write_available": write_available,
        "last_checked_at": _utc_now(),
        "source_of_truth": SOURCE_OF_TRUTH,
        "blocking_reason": blocking_reason,
        "recovery_action": recovery_action,
        "auth_status": auth_status,
        "display_status": display_status,
        "status": display_status,
        "connected": display_status in {"connected", "syncing"},
        "raw_status": raw_status,
        "environment": env,
        "name": str(row.get("name") or vendor or "connector"),
    }


def list_connector_availability(
    client: Any,
    org_id: str,
    settings: Settings,
    *,
    environment_name: str = "production",
    force_live: bool = False,
    action_key: str | None = None,
) -> list[dict[str, Any]]:
    rows = list_connectors(client, org_id, environment_name=environment_name)
    return [
        evaluate_connector_availability(
            client,
            org_id,
            row,
            settings,
            environment_name=environment_name,
            force_live=force_live,
            action_key=action_key,
        )
        for row in rows
    ]


def list_executable_integrations(
    client: Any,
    org_id: str,
    settings: Settings,
    *,
    environment_name: str = "production",
    force_live: bool = True,
    action_key: str | None = None,
) -> list[str]:
    integrations: set[str] = set()
    for item in list_connector_availability(
        client,
        org_id,
        settings,
        environment_name=environment_name,
        force_live=force_live,
        action_key=action_key,
    ):
        if not item.get("execution_available"):
            continue
        vendor = _normalize_vendor(str(item.get("vendor") or ""))
        if vendor:
            integrations.add(vendor)
    return sorted(integrations)


def find_integration_availability(
    client: Any,
    org_id: str,
    integration: str,
    settings: Settings,
    *,
    environment_name: str = "production",
    force_live: bool = True,
    action_key: str | None = None,
) -> dict[str, Any] | None:
    target = _normalize_vendor(integration)
    matches = [
        item
        for item in list_connector_availability(
            client,
            org_id,
            settings,
            environment_name=environment_name,
            force_live=force_live,
            action_key=action_key,
        )
        if _normalize_vendor(str(item.get("vendor") or "")) == target
    ]
    if not matches:
        return None
    return max(matches, key=lambda item: bool(item.get("execution_available")))


def error_code_for_unavailable_integration(
    availability: dict[str, Any] | None,
) -> str:
    """Map connector availability to chat/clarify chip errorCode.

    Expired OAuth must surface as ``auth_expired`` (reconnect copy), not
    ``tool_not_available`` (which implies the connector was never connected /
    not permitted for the agent).
    """
    if not availability:
        return "tool_not_available"
    auth = str(availability.get("auth_status") or "").strip().lower()
    reason = str(availability.get("blocking_reason") or "").strip().lower()
    if auth == "auth_expired" or reason == "token_expired":
        return "auth_expired"
    if reason == "missing_scope":
        return "permission_denied"
    return "tool_not_available"


def format_connector_blocking_message(
    integration: str,
    availability: dict[str, Any] | None,
    *,
    action_key: str | None = None,
) -> str:
    vendor_label = integration.replace("_", " ").title()
    if availability is None:
        return (
            f"No {vendor_label} connector is configured for this organization. "
            f"Add and connect {vendor_label} under Connectors, then retry."
        )
    if availability.get("execution_available"):
        return f"{vendor_label} is connected and ready."

    reason = str(availability.get("blocking_reason") or "not_available")
    recovery = str(availability.get("recovery_action") or "").strip()
    action_label = (action_key or "this action").replace(".", " ")

    if reason == "token_expired":
        return recovery or f"{vendor_label} is configured, but authentication has expired. Reconnect {vendor_label}."
    if reason == "missing_scope":
        if action_key:
            return (
                f"{vendor_label} is connected, but {action_label} is not executable because required OAuth scopes are missing. "
                f"Reconnect {vendor_label} and approve the requested permissions."
            )
        return recovery or f"{vendor_label} is connected, but required OAuth scopes are missing."
    if reason == "unsupported_action" and action_key:
        return (
            f"{vendor_label} is connected, but {action_label} is not executable because the action is not supported yet."
        )
    if reason == "pending_auth":
        return recovery or f"{vendor_label} is configured but not authenticated. Complete OAuth on the Connectors page."
    if reason == "misconfigured":
        return recovery or f"{vendor_label} is not fully configured yet."
    return recovery or f"{vendor_label} is not available for connector actions right now."


class ConnectorAvailabilityService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def list_for_org(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str = "production",
        force_live: bool = False,
        action_key: str | None = None,
    ) -> list[dict[str, Any]]:
        return list_connector_availability(
            client,
            org_id,
            self.settings,
            environment_name=environment_name,
            force_live=force_live,
            action_key=action_key,
        )

    def list_executable_integrations(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str = "production",
        force_live: bool = True,
        action_key: str | None = None,
    ) -> list[str]:
        return list_executable_integrations(
            client,
            org_id,
            self.settings,
            environment_name=environment_name,
            force_live=force_live,
            action_key=action_key,
        )

    def find_integration(
        self,
        client: Any,
        org_id: str,
        integration: str,
        *,
        environment_name: str = "production",
        force_live: bool = True,
        action_key: str | None = None,
    ) -> dict[str, Any] | None:
        return find_integration_availability(
            client,
            org_id,
            integration,
            self.settings,
            environment_name=environment_name,
            force_live=force_live,
            action_key=action_key,
        )

    def format_blocking_message(
        self,
        integration: str,
        availability: dict[str, Any] | None,
        *,
        action_key: str | None = None,
    ) -> str:
        return format_connector_blocking_message(integration, availability, action_key=action_key)


_service: ConnectorAvailabilityService | None = None


def get_connector_availability_service(settings: Settings | None = None) -> ConnectorAvailabilityService:
    global _service
    if _service is None or settings is not None:
        _service = ConnectorAvailabilityService(settings)
    return _service
