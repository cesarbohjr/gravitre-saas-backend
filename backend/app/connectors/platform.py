"""Shared connector platform helpers (OAuth reuse, API key storage).

All Tier 1/2 (and future) integrations should use these helpers so connect,
reconnect, delete, and API-key flows behave consistently.
"""
from __future__ import annotations

from fastapi import HTTPException, status

from app.config import Settings
from app.connectors.google_vendor_oauth import GOOGLE_OAUTH_VENDORS, VENDOR_DOCS as GOOGLE_VENDOR_DOCS
from app.connectors.hubspot_oauth import normalize_vendor
from app.connectors.repository import get_decrypted_secret, set_secret
from app.core.crypto import decrypt_value, encrypt_value, mask_value
from app.core.errors import error_detail

OAUTH_DOCS_URLS: dict[str, str] = {
    "hubspot": "https://developers.hubspot.com/docs",
    "salesforce": "https://developer.salesforce.com/docs",
    "quickbooks": "https://developer.intuit.com/app/developer/qbo/docs",
    "netsuite": "https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_1540391670.html",
    "jira": "https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/",
    "confluence": "https://developer.atlassian.com/cloud/confluence/oauth-2-3lo-apps/",
    "pagerduty": "https://developer.pagerduty.com/docs/72d3b724589e3-oauth-functionality",
    "notion": "https://developers.notion.com/docs/authorization",
    "marketo": "https://developers.marketo.com/rest-api/",
    "slack": "https://api.slack.com/authentication/oauth-v2",
}


def oauth_docs_url(vendor: str) -> str:
    if vendor in GOOGLE_OAUTH_VENDORS:
        return GOOGLE_VENDOR_DOCS.get(vendor) or ""
    return OAUTH_DOCS_URLS.get(vendor, "")


def find_existing_oauth_connector(
    client,
    org_id: str,
    vendor: str,
    name: str,
) -> dict | None:
    """Find connector row to reuse for OAuth (org_id + name is unique)."""
    normalized_name = name.strip()
    by_name = (
        client.table("connectors")
        .select("id, vendor, type, name, status, environment")
        .eq("org_id", org_id)
        .eq("name", normalized_name)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if by_name.data:
        row = by_name.data[0]
        existing_vendor = normalize_vendor(row.get("vendor") or row.get("type") or "")
        if existing_vendor and existing_vendor != vendor:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_detail(
                    f"A connector named {normalized_name!r} already exists for another integration",
                    "CONNECTOR_NAME_CONFLICT",
                ),
            )
        return row

    by_vendor = (
        client.table("connectors")
        .select("id, vendor, type, name, status, environment")
        .eq("org_id", org_id)
        .eq("vendor", vendor)
        .is_("deleted_at", "null")
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    if by_vendor.data:
        return by_vendor.data[0]
    return None


def mark_connector_pending_oauth(
    client,
    *,
    org_id: str,
    connector_id: str,
    vendor: str,
    environment_name: str,
) -> None:
    client.table("connectors").update(
        {
            "status": "pending_auth",
            "environment": environment_name,
            "vendor": vendor,
            "type": vendor,
            "description": f"{vendor.replace('_', ' ').title()} (OAuth)",
            "sync_frequency": "1h",
            "config": {"auth_type": "oauth"},
            "docs_url": oauth_docs_url(vendor),
        }
    ).eq("id", connector_id).eq("org_id", org_id).execute()


def prepare_oauth_connector(
    client,
    *,
    org_id: str,
    vendor: str,
    name: str,
    environment_name: str,
) -> tuple[str, bool, bool]:
    """Create or reuse pending_auth connector. Returns (connector_id, reconnect, is_new)."""
    docs_url = oauth_docs_url(vendor)
    existing = find_existing_oauth_connector(client, org_id, vendor, name)
    if existing:
        connector_id = str(existing["id"])
        prior_status = str(existing.get("status") or "")
        reconnect = prior_status not in {"", "pending_auth", "disconnected"}
        mark_connector_pending_oauth(
            client,
            org_id=org_id,
            connector_id=connector_id,
            vendor=vendor,
            environment_name=environment_name,
        )
        return connector_id, reconnect, False

    row = {
        "org_id": org_id,
        "name": name.strip(),
        "vendor": vendor,
        "type": vendor,
        "description": f"{vendor.replace('_', ' ').title()} (OAuth)",
        "status": "pending_auth",
        "environment": environment_name,
        "sync_frequency": "1h",
        "config": {"auth_type": "oauth"},
        "docs_url": docs_url,
    }
    created = client.table("connectors").insert(row).execute()
    if not created.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Connector create failed")
    return str(created.data[0]["id"]), False, True


def store_connector_api_key(
    client,
    org_id: str,
    connector_id: str,
    api_key: str,
    settings: Settings,
) -> str | None:
    """Persist API key via connector_secrets (preferred) or legacy column encryption."""
    plain = (api_key or "").strip()
    if not plain:
        return None
    if (settings.connector_secrets_encryption_key or "").strip():
        set_secret(client, org_id, connector_id, "api_key", plain, settings)
        return None
    if (settings.encryption_key or "").strip():
        return encrypt_value(plain, settings.encryption_key)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=error_detail(
            "API key encryption is not configured (set CONNECTOR_SECRETS_ENCRYPTION_KEY)",
            "INVALID_CONFIG",
        ),
    )


def read_masked_api_key(
    client,
    connector_id: str,
    row: dict,
    settings: Settings,
) -> str | None:
    secret = get_decrypted_secret(client, connector_id, "api_key", settings)
    if secret:
        return secret
    encrypted = row.get("api_key_encrypted")
    if encrypted and (settings.encryption_key or "").strip():
        try:
            return decrypt_value(encrypted, settings.encryption_key)
        except Exception:
            return None
    return None


def masked_api_key_for_response(
    client,
    connector_id: str,
    row: dict,
    settings: Settings,
) -> str | None:
    return mask_value(read_masked_api_key(client, connector_id, row, settings))
