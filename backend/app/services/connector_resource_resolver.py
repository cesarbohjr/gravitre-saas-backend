"""Resolve connector-owned resources without asking the user first."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

ResourceStatus = Literal["resolved", "ambiguous", "not_found", "not_authorized", "unavailable"]


@dataclass(frozen=True)
class ResourceResolution:
    status: ResourceStatus
    connector_id: str
    connection_id: str | None = None
    resource_type: str = ""
    resource_id: str = ""
    display_name: str = ""
    confidence: float = 0.0
    resolution_reason: str = ""
    candidate_count: int = 0
    candidates: tuple[dict[str, Any], ...] = field(default_factory=tuple)


def _connector_row(client: Any, org_id: str, connector_id: str) -> dict[str, Any] | None:
    from app.connectors.repository import get_connector_by_type

    row = get_connector_by_type(client, org_id, connector_id, environment_name="default")
    if isinstance(row, dict) and row.get("id"):
        return row
    return None


def _config_property_id(conn: dict[str, Any]) -> str:
    cfg = conn.get("config") if isinstance(conn.get("config"), dict) else {}
    return str(cfg.get("property_id") or cfg.get("propertyId") or "").strip()


def _config_property_name(conn: dict[str, Any]) -> str:
    cfg = conn.get("config") if isinstance(conn.get("config"), dict) else {}
    return str(cfg.get("property_name") or cfg.get("propertyName") or "").strip()


def resolve_ga4_property(
    *,
    client: Any,
    org_id: str,
    settings: Settings,
    environment_name: str = "default",
) -> ResourceResolution:
    """Discover GA4 property from linked config or Admin API listing."""
    connector_id = "google_analytics"
    conn = _connector_row(client, org_id, connector_id)
    if not conn:
        return ResourceResolution(
            status="not_found",
            connector_id=connector_id,
            resource_type="property",
            resolution_reason="connector_not_configured",
        )

    connection_id = str(conn.get("id") or "")
    linked_id = _config_property_id(conn)
    linked_name = _config_property_name(conn)
    if linked_id:
        return ResourceResolution(
            status="resolved",
            connector_id=connector_id,
            connection_id=connection_id,
            resource_type="property",
            resource_id=linked_id,
            display_name=linked_name or f"Property {linked_id}",
            confidence=0.98,
            resolution_reason="linked_config",
            candidate_count=1,
        )

    from app.connectors.google_analytics_oauth import ensure_google_analytics_session
    from app.connectors.google_analytics import GoogleAnalyticsAPIError, list_ga4_properties

    token, err = ensure_google_analytics_session(
        client,
        org_id,
        connection_id,
        settings,
        environment_name=str(conn.get("environment") or environment_name),
    )
    if err or not token:
        return ResourceResolution(
            status="not_authorized",
            connector_id=connector_id,
            connection_id=connection_id,
            resource_type="property",
            resolution_reason=str(err or "auth_failed"),
        )

    try:
        properties = list_ga4_properties(token)
    except GoogleAnalyticsAPIError as exc:
        logger.warning("ga4_property_list_failed org=%s err=%s", org_id, exc)
        return ResourceResolution(
            status="unavailable",
            connector_id=connector_id,
            connection_id=connection_id,
            resource_type="property",
            resolution_reason=str(exc),
        )

    if not properties:
        return ResourceResolution(
            status="not_found",
            connector_id=connector_id,
            connection_id=connection_id,
            resource_type="property",
            resolution_reason="no_properties_in_account",
            candidate_count=0,
        )

    if len(properties) == 1:
        prop = properties[0]
        return ResourceResolution(
            status="resolved",
            connector_id=connector_id,
            connection_id=connection_id,
            resource_type="property",
            resource_id=str(prop.get("property_id") or ""),
            display_name=str(prop.get("display_name") or prop.get("property_id") or ""),
            confidence=0.95,
            resolution_reason="single_discovered_property",
            candidate_count=1,
            candidates=(prop,),
        )

    return ResourceResolution(
        status="ambiguous",
        connector_id=connector_id,
        connection_id=connection_id,
        resource_type="property",
        resolution_reason="multiple_properties",
        candidate_count=len(properties),
        candidates=tuple(properties),
    )


def resolve_resource(
    *,
    connector_id: str,
    client: Any,
    org_id: str,
    settings: Settings,
    resource_type: str | None = None,
    environment_name: str = "default",
) -> ResourceResolution:
    """Generic entry — vendor-specific resolvers added incrementally."""
    vendor = str(connector_id or "").strip().lower()
    rtype = str(resource_type or "").strip().lower()
    if vendor == "google_analytics" and (not rtype or rtype == "property"):
        return resolve_ga4_property(
            client=client,
            org_id=org_id,
            settings=settings,
            environment_name=environment_name,
        )
    return ResourceResolution(
        status="unavailable",
        connector_id=vendor,
        resource_type=rtype or "unknown",
        resolution_reason="resolver_not_implemented",
    )
