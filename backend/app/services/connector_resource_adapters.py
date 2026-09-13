"""Per-vendor resource discovery adapters for ConnectorResourceResolver."""
from __future__ import annotations

from typing import Any, Callable

from app.config import Settings
from app.services.connector_resource_resolver import ResourceResolution

AdapterFn = Callable[..., ResourceResolution]


def _config_value(conn: dict[str, Any], *keys: str) -> str:
    cfg = conn.get("config") if isinstance(conn.get("config"), dict) else {}
    for key in keys:
        value = str(cfg.get(key) or "").strip()
        if value:
            return value
    return ""


def _resolved_connection(
    *,
    connector_id: str,
    connection_id: str,
    resource_type: str,
    resource_id: str,
    display_name: str,
    reason: str,
    confidence: float = 0.92,
) -> ResourceResolution:
    return ResourceResolution(
        status="resolved",
        connector_id=connector_id,
        connection_id=connection_id,
        resource_type=resource_type,
        resource_id=resource_id,
        display_name=display_name,
        confidence=confidence,
        resolution_reason=reason,
        candidate_count=1,
    )


def resolve_connection_only(
    *,
    connector_id: str,
    conn: dict[str, Any],
    resource_type: str = "connection",
    display_field: str = "name",
) -> ResourceResolution:
    connection_id = str(conn.get("id") or "")
    cfg = conn.get("config") if isinstance(conn.get("config"), dict) else {}
    label = str(conn.get(display_field) or cfg.get("display_name") or connector_id.replace("_", " ").title())
    return _resolved_connection(
        connector_id=connector_id,
        connection_id=connection_id,
        resource_type=resource_type,
        resource_id=connection_id,
        display_name=label,
        reason="single_connection",
    )


def resolve_hubspot(
    *,
    client: Any,
    org_id: str,
    settings: Settings,
    conn: dict[str, Any],
    environment_name: str,
) -> ResourceResolution:
    del client, org_id, settings, environment_name
    portal = _config_value(conn, "portal_id", "portalId", "hub_id", "hubId")
    if portal:
        return _resolved_connection(
            connector_id="hubspot",
            connection_id=str(conn.get("id") or ""),
            resource_type="portal",
            resource_id=portal,
            display_name=f"HubSpot portal {portal}",
            reason="linked_portal_config",
        )
    return resolve_connection_only(connector_id="hubspot", conn=conn, resource_type="portal")


def resolve_salesforce(
    *,
    client: Any,
    org_id: str,
    settings: Settings,
    conn: dict[str, Any],
    environment_name: str,
) -> ResourceResolution:
    del settings, environment_name
    instance = _config_value(conn, "instance_url", "instanceUrl")
    if not instance:
        from app.connectors.salesforce_oauth import _connector_instance_url

        instance = _connector_instance_url(client, org_id, str(conn.get("id") or "")) or ""
    if instance:
        return _resolved_connection(
            connector_id="salesforce",
            connection_id=str(conn.get("id") or ""),
            resource_type="org",
            resource_id=instance,
            display_name=instance.replace("https://", "").split(".")[0],
            reason="linked_instance_config",
        )
    return resolve_connection_only(connector_id="salesforce", conn=conn, resource_type="org")


def resolve_slack(*, conn: dict[str, Any], **_: Any) -> ResourceResolution:
    team = _config_value(conn, "team_id", "teamId", "workspace_id", "workspaceId")
    team_name = _config_value(conn, "team_name", "teamName", "workspace_name", "workspaceName")
    if team:
        return _resolved_connection(
            connector_id="slack",
            connection_id=str(conn.get("id") or ""),
            resource_type="workspace",
            resource_id=team,
            display_name=team_name or f"Slack workspace {team}",
            reason="linked_workspace_config",
        )
    return resolve_connection_only(connector_id="slack", conn=conn, resource_type="workspace")


def resolve_github(*, conn: dict[str, Any], **_: Any) -> ResourceResolution:
    org = _config_value(conn, "org", "organization", "login", "owner")
    if org:
        return _resolved_connection(
            connector_id="github",
            connection_id=str(conn.get("id") or ""),
            resource_type="org",
            resource_id=org,
            display_name=org,
            reason="linked_org_config",
        )
    return resolve_connection_only(connector_id="github", conn=conn, resource_type="org")


def resolve_microsoft365(*, conn: dict[str, Any], **_: Any) -> ResourceResolution:
    tenant = _config_value(conn, "tenant_id", "tenantId")
    if tenant:
        return _resolved_connection(
            connector_id="microsoft365",
            connection_id=str(conn.get("id") or ""),
            resource_type="tenant",
            resource_id=tenant,
            display_name=f"Microsoft 365 tenant",
            reason="linked_tenant_config",
        )
    return resolve_connection_only(connector_id="microsoft365", conn=conn, resource_type="tenant")


def resolve_quickbooks(
    *,
    client: Any,
    org_id: str,
    settings: Settings,
    conn: dict[str, Any],
    environment_name: str,
) -> ResourceResolution:
    del client, org_id, settings, environment_name
    realm = _config_value(conn, "realm_id", "realmId", "company_id", "companyId")
    company = _config_value(conn, "company_name", "companyName")
    if realm:
        return _resolved_connection(
            connector_id="quickbooks",
            connection_id=str(conn.get("id") or ""),
            resource_type="company",
            resource_id=realm,
            display_name=company or f"QuickBooks company {realm}",
            reason="linked_realm_config",
        )
    return resolve_connection_only(connector_id="quickbooks", conn=conn, resource_type="company")


def resolve_gsc_site(
    *,
    client: Any,
    org_id: str,
    settings: Settings,
    conn: dict[str, Any],
    environment_name: str,
) -> ResourceResolution:
    from app.connectors.google_search_console import GoogleSearchConsoleAPIError, list_gsc_sites
    from app.connectors.google_vendor_oauth import ensure_google_vendor_session

    connector_id = "google_search_console"
    connection_id = str(conn.get("id") or "")
    linked = _config_value(conn, "site_url", "siteUrl")
    if linked:
        return _resolved_connection(
            connector_id=connector_id,
            connection_id=connection_id,
            resource_type="site",
            resource_id=linked,
            display_name=linked,
            reason="linked_config",
            confidence=0.98,
        )

    token, err = ensure_google_vendor_session(
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
            resource_type="site",
            resolution_reason=str(err or "auth_failed"),
        )
    try:
        sites = list_gsc_sites(token)
    except GoogleSearchConsoleAPIError as exc:
        return ResourceResolution(
            status="unavailable",
            connector_id=connector_id,
            connection_id=connection_id,
            resource_type="site",
            resolution_reason=str(exc),
        )
    if not sites:
        return ResourceResolution(
            status="not_found",
            connector_id=connector_id,
            connection_id=connection_id,
            resource_type="site",
            resolution_reason="no_sites_in_account",
            candidate_count=0,
        )
    if len(sites) == 1:
        site = sites[0]
        site_url = str(site.get("site_url") or "")
        return _resolved_connection(
            connector_id=connector_id,
            connection_id=connection_id,
            resource_type="site",
            resource_id=site_url,
            display_name=site_url,
            reason="single_discovered_site",
            confidence=0.95,
        )
    return ResourceResolution(
        status="ambiguous",
        connector_id=connector_id,
        connection_id=connection_id,
        resource_type="site",
        resolution_reason="multiple_sites",
        candidate_count=len(sites),
        candidates=tuple(sites),
    )


def resolve_google_ads_customer(
    *,
    client: Any,
    org_id: str,
    settings: Settings,
    conn: dict[str, Any],
    environment_name: str,
) -> ResourceResolution:
    from app.connectors.google_ads import GoogleAdsAPIError, list_accessible_customers
    from app.connectors.google_vendor_oauth import ensure_google_vendor_session

    connector_id = "google_ads"
    connection_id = str(conn.get("id") or "")
    linked = _config_value(conn, "customer_id", "customerId").replace("-", "")
    if linked:
        return _resolved_connection(
            connector_id=connector_id,
            connection_id=connection_id,
            resource_type="customer",
            resource_id=linked,
            display_name=f"Ads customer {linked}",
            reason="linked_config",
            confidence=0.98,
        )

    token, err = ensure_google_vendor_session(
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
            resource_type="customer",
            resolution_reason=str(err or "auth_failed"),
        )
    developer_token = str(getattr(settings, "google_ads_developer_token", "") or "").strip()
    try:
        customers = list_accessible_customers(token, developer_token=developer_token)
    except GoogleAdsAPIError as exc:
        return ResourceResolution(
            status="unavailable",
            connector_id=connector_id,
            connection_id=connection_id,
            resource_type="customer",
            resolution_reason=str(exc),
        )
    if not customers:
        return ResourceResolution(
            status="not_found",
            connector_id=connector_id,
            connection_id=connection_id,
            resource_type="customer",
            resolution_reason="no_customers_in_account",
            candidate_count=0,
        )
    if len(customers) == 1:
        customer = customers[0]
        cid = str(customer.get("customer_id") or customer.get("id") or "")
        return _resolved_connection(
            connector_id=connector_id,
            connection_id=connection_id,
            resource_type="customer",
            resource_id=cid,
            display_name=str(customer.get("descriptive_name") or f"Ads customer {cid}"),
            reason="single_discovered_customer",
            confidence=0.95,
        )
    return ResourceResolution(
        status="ambiguous",
        connector_id=connector_id,
        connection_id=connection_id,
        resource_type="customer",
        resolution_reason="multiple_customers",
        candidate_count=len(customers),
        candidates=tuple(customers),
    )


RESOURCE_ADAPTER_REGISTRY: dict[str, AdapterFn] = {
    "hubspot": resolve_hubspot,
    "salesforce": resolve_salesforce,
    "slack": resolve_slack,
    "github": resolve_github,
    "microsoft365": resolve_microsoft365,
    "quickbooks": resolve_quickbooks,
    "google_search_console": resolve_gsc_site,
    "google_ads": resolve_google_ads_customer,
}
