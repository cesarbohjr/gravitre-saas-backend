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


@dataclass(frozen=True)
class ResourceResolutionRequest:
    tenant_id: str
    user_id: str | None = None
    connector_id: str = ""
    requested_capability: str | None = None
    requested_resource_type: str | None = None
    conversation_context: dict[str, Any] | None = None
    environment_name: str = "default"


def _connector_row(
    client: Any,
    org_id: str,
    connector_id: str,
    *,
    environment_name: str = "production",
    override: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if isinstance(override, dict) and (override.get("id") or override.get("config") or override.get("type")):
        return override
    from app.connectors.repository import get_connector_by_type

    row = get_connector_by_type(
        client, org_id, connector_id, environment_name=environment_name
    )
    if isinstance(row, dict) and row.get("id"):
        return row
    return None


def _config_property_id(conn: dict[str, Any]) -> str:
    cfg = conn.get("config") if isinstance(conn.get("config"), dict) else {}
    return str(cfg.get("property_id") or cfg.get("propertyId") or "").strip()


def _config_property_name(conn: dict[str, Any]) -> str:
    cfg = conn.get("config") if isinstance(conn.get("config"), dict) else {}
    return str(cfg.get("property_name") or cfg.get("propertyName") or "").strip()


def _context_resource_hint(context: dict[str, Any] | None, connector_id: str) -> str | None:
    if not isinstance(context, dict):
        return None
    session = context.get("connector_session") if isinstance(context.get("connector_session"), dict) else {}
    resolved = session.get("resolvedEntities") if isinstance(session.get("resolvedEntities"), dict) else {}
    active = session.get("activeEntities") if isinstance(session.get("activeEntities"), dict) else {}
    if connector_id == "google_analytics":
        for bucket in (active, resolved, context.get("resolved_entities") or {}):
            if not isinstance(bucket, dict):
                continue
            overview = bucket.get("analytics_traffic_overview")
            if isinstance(overview, dict) and overview.get("propertyId"):
                return str(overview.get("propertyId"))
            if bucket.get("property_id"):
                return str(bucket.get("property_id"))
    if connector_id == "google_search_console":
        for bucket in (resolved, context.get("resolved_entities") or {}):
            if isinstance(bucket, dict) and bucket.get("site_url"):
                return str(bucket.get("site_url"))
    return None


def resolve_ga4_property(
    *,
    client: Any,
    org_id: str,
    settings: Settings,
    environment_name: str = "default",
    conversation_context: dict[str, Any] | None = None,
) -> ResourceResolution:
    """Discover GA4 property from linked config or Admin API listing."""
    connector_id = "google_analytics"
    override = None
    if isinstance(conversation_context, dict):
        raw = conversation_context.get("_connector_row")
        override = raw if isinstance(raw, dict) else None
    conn = _connector_row(
        client, org_id, connector_id, environment_name=environment_name, override=override
    )
    if not conn:
        return ResourceResolution(
            status="not_found",
            connector_id=connector_id,
            resource_type="property",
            resolution_reason="connector_not_configured",
        )

    connection_id = str(conn.get("id") or "")
    hint = _context_resource_hint(conversation_context, connector_id)
    linked_id = _config_property_id(conn) or (hint or "")
    linked_name = _config_property_name(conn)
    if linked_id:
        return ResourceResolution(
            status="resolved",
            connector_id=connector_id,
            connection_id=connection_id,
            resource_type="property",
            resource_id=linked_id,
            display_name=linked_name or f"Property {linked_id}",
            confidence=0.98 if _config_property_id(conn) else 0.9,  # confidence-honesty-ok: resolution prior
            resolution_reason="linked_config" if _config_property_id(conn) else "conversation_context",
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
            confidence=0.95,  # confidence-honesty-ok: single-candidate discovery prior
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
    conversation_context: dict[str, Any] | None = None,
    connector_row: dict[str, Any] | None = None,
) -> ResourceResolution:
    """Generic entry — dispatches to vendor-specific adapters."""
    vendor = str(connector_id or "").strip().lower()
    rtype = str(resource_type or "").strip().lower()
    override = connector_row
    if override is None and isinstance(conversation_context, dict):
        raw = conversation_context.get("_connector_row")
        override = raw if isinstance(raw, dict) else None

    if vendor == "google_analytics" and (not rtype or rtype == "property"):
        merged_ctx = dict(conversation_context or {})
        if override:
            merged_ctx["_connector_row"] = override
        return resolve_ga4_property(
            client=client,
            org_id=org_id,
            settings=settings,
            environment_name=environment_name,
            conversation_context=merged_ctx,
        )

    conn = _connector_row(
        client, org_id, vendor, environment_name=environment_name, override=override
    )
    if not conn:
        return ResourceResolution(
            status="not_found",
            connector_id=vendor,
            resource_type=rtype or "connection",
            resolution_reason="connector_not_configured",
        )

    from app.services.connector_resource_adapters import RESOURCE_ADAPTER_REGISTRY

    adapter = RESOURCE_ADAPTER_REGISTRY.get(vendor)
    if adapter is None:
        return ResourceResolution(
            status="unavailable",
            connector_id=vendor,
            resource_type=rtype or "unknown",
            resolution_reason="resolver_not_implemented",
        )

    return adapter(
        client=client,
        org_id=org_id,
        settings=settings,
        conn=conn,
        environment_name=environment_name,
    )


def resolve_resource_request(
    request: ResourceResolutionRequest,
    *,
    client: Any,
    settings: Settings,
) -> ResourceResolution:
    """Structured resolveResource entry used by the cognitive resolution pipeline."""
    return resolve_resource(
        connector_id=request.connector_id,
        client=client,
        org_id=request.tenant_id,
        settings=settings,
        resource_type=request.requested_resource_type,
        environment_name=request.environment_name,
        conversation_context=request.conversation_context,
    )
