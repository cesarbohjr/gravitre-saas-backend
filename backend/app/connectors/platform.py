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
    "pipedrive": "https://developers.pipedrive.com/docs/api/v1/OAuth-2.0",
}


def oauth_docs_url(vendor: str) -> str:
    if vendor in GOOGLE_OAUTH_VENDORS:
        return GOOGLE_VENDOR_DOCS.get(vendor) or ""
    return OAUTH_DOCS_URLS.get(vendor, "")


def _is_duplicate_connector_name_error(exc: BaseException) -> bool:
    if getattr(exc, "code", None) == "23505":
        return True
    msg = str(exc)
    return "23505" in msg or "connectors_org_name_key" in msg


def is_connector_type_schema_error(exc: BaseException) -> bool:
    if getattr(exc, "code", None) == "23514":
        return True
    msg = str(exc)
    return "23514" in msg or "connectors_type_check" in msg


def raise_connector_type_schema_error(exc: BaseException) -> None:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=error_detail(
            "Connector type is not enabled in the database. Apply the latest Supabase migration "
            "(supabase db push) or run supabase/migrations/20260625120000_expand_connector_types_full_catalog.sql.",
            "CONNECTOR_TYPE_SCHEMA_OUTDATED",
        ),
    ) from exc


def _is_connector_type_check_error(exc: BaseException) -> bool:
    return is_connector_type_schema_error(exc)


def _raise_connector_type_schema_error(exc: BaseException) -> None:
    raise_connector_type_schema_error(exc)


def _fetch_connector_by_vendor(
    client,
    org_id: str,
    vendor: str,
    *,
    include_deleted: bool = False,
) -> dict | None:
    for column in ("vendor", "type"):
        query = (
            client.table("connectors")
            .select("id, vendor, type, name, status, environment, deleted_at")
            .eq("org_id", org_id)
            .eq(column, vendor)
        )
        if not include_deleted:
            query = query.is_("deleted_at", "null")
        result = query.order("updated_at", desc=True).limit(1).execute()
        if result.data:
            return result.data[0]
    return None


def _fetch_connector_by_org_name(
    client,
    org_id: str,
    name: str,
    *,
    include_deleted: bool = False,
) -> dict | None:
    normalized_name = name.strip()
    query = (
        client.table("connectors")
        .select("id, vendor, type, name, status, environment, deleted_at")
        .eq("org_id", org_id)
        .eq("name", normalized_name)
    )
    if not include_deleted:
        query = query.is_("deleted_at", "null")
    result = query.limit(1).execute()
    if result.data:
        return result.data[0]
    return None


def _validate_oauth_connector_reuse(row: dict, vendor: str, normalized_name: str) -> None:
    existing_vendor = normalize_vendor(row.get("vendor") or row.get("type") or "")
    if existing_vendor and existing_vendor != vendor:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_detail(
                f"A connector named {normalized_name!r} already exists for another integration",
                "CONNECTOR_NAME_CONFLICT",
            ),
        )


def _reuse_oauth_connector(
    client,
    *,
    org_id: str,
    connector_id: str,
    vendor: str,
    environment_name: str,
    prior_status: str,
) -> tuple[str, bool, bool]:
    reconnect = prior_status not in {"", "pending_auth", "disconnected"}
    mark_connector_pending_oauth(
        client,
        org_id=org_id,
        connector_id=connector_id,
        vendor=vendor,
        environment_name=environment_name,
    )
    return connector_id, reconnect, False


def find_existing_oauth_connector(
    client,
    org_id: str,
    vendor: str,
    name: str,
) -> dict | None:
    """Find connector row to reuse for OAuth (org_id + name is unique)."""
    normalized_name = name.strip()
    for include_deleted in (False, True):
        by_name = _fetch_connector_by_org_name(
            client, org_id, normalized_name, include_deleted=include_deleted
        )
        if by_name:
            _validate_oauth_connector_reuse(by_name, vendor, normalized_name)
            return by_name

        by_vendor = _fetch_connector_by_vendor(
            client, org_id, vendor, include_deleted=include_deleted
        )
        if by_vendor:
            return by_vendor
    return None


def clear_connector_oauth_tokens(client, connector_id: str) -> None:
    """Drop stored OAuth tokens so auth status cannot stay 'connected' after delete/re-auth."""
    try:
        (
            client.table("connector_secrets")
            .delete()
            .eq("connector_id", connector_id)
            .eq("key_name", "oauth_tokens")
            .execute()
        )
    except Exception:  # noqa: BLE001
        # Best-effort — status update below still moves the row to pending_auth.
        pass


def mark_connector_pending_oauth(
    client,
    *,
    org_id: str,
    connector_id: str,
    vendor: str,
    environment_name: str,
) -> None:
    # Clear prior tokens before OAuth so a failed HubSpot authorize (or soft-delete
    # resurrection) cannot leave the UI showing "connected" from stale secrets.
    clear_connector_oauth_tokens(client, connector_id)
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
            "deleted_at": None,
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
        return _reuse_oauth_connector(
            client,
            org_id=org_id,
            connector_id=str(existing["id"]),
            vendor=vendor,
            environment_name=environment_name,
            prior_status=str(existing.get("status") or ""),
        )

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
    try:
        created = client.table("connectors").insert(row).execute()
        if not created.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Connector create failed")
        return str(created.data[0]["id"]), False, True
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        if _is_connector_type_check_error(exc):
            _raise_connector_type_schema_error(exc)
        if not _is_duplicate_connector_name_error(exc):
            raise
        recovered = find_existing_oauth_connector(client, org_id, vendor, name)
        if not recovered:
            recovered = _fetch_connector_by_org_name(client, org_id, name.strip(), include_deleted=True)
        if not recovered:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_detail("Connector name already exists", "CONNECTOR_NAME_CONFLICT"),
            ) from exc
        return _reuse_oauth_connector(
            client,
            org_id=org_id,
            connector_id=str(recovered["id"]),
            vendor=vendor,
            environment_name=environment_name,
            prior_status=str(recovered.get("status") or ""),
        )


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
