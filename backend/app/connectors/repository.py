"""IN-00: Connector CRUD and secrets. Never return secrets to callers."""
from __future__ import annotations

from supabase import Client

from app.connectors.constants import (
    ACTIVE_CONNECTOR_STATUSES,
    connector_environment_candidates,
    normalize_environment_name,
)
from app.connectors.crypto import decrypt_secret, encrypt_secret
from app.config import Settings
from app.services.data_residency_service import enforce_region_for_connector_tokens, get_org_data_region
from app.core.safe_dict import safe_normalize_stored_dict


def _org_residency(client: Client, org_id: str) -> str:
    row = (
        client.table("organizations")
        .select("settings,data_region")
        .eq("id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        return "us"
    org_row = row.data[0]
    settings = org_row.get("settings") or {}
    org_settings = settings if isinstance(settings, dict) else {}
    return get_org_data_region(org_settings, data_region=org_row.get("data_region"))


def _connector_data_region(client: Client, org_id: str, connector_id: str) -> str | None:
    row = (
        client.table("connectors")
        .select("config")
        .eq("org_id", org_id)
        .eq("id", connector_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        return None
    config = row.data[0].get("config") or {}
    if not isinstance(config, dict):
        return None
    region = config.get("dataRegion") or config.get("data_region")
    return str(region) if region else None


def _query_connectors_for_env(
    client: Client,
    org_id: str,
    environment_name: str,
) -> list[dict]:
    env = normalize_environment_name(environment_name)
    r = (
        client.table("connectors")
        .select("id, org_id, name, type, vendor, status, config, environment, created_at, updated_at")
        .eq("org_id", org_id)
        .eq("environment", env)
        .is_("deleted_at", "null")
        .order("created_at", desc=True)
        .execute()
    )
    return [dict(row) for row in (r.data or [])]


def list_connectors(client: Client, org_id: str, environment_name: str = "production") -> list[dict]:
    """List connectors for org and environment. No secrets."""
    rows = _query_connectors_for_env(client, org_id, environment_name)
    if rows:
        return rows
    # Fallback: legacy rows may live under default while UI/chat use production.
    primary = normalize_environment_name(environment_name)
    if primary == "production":
        legacy = _query_connectors_for_env(client, org_id, "default")
        if legacy:
            return legacy
    return rows


def get_connector_by_type(
    client: Client,
    org_id: str,
    connector_type: str,
    environment_name: str = "production",
) -> dict | None:
    """Get first usable connector of type for org (active, healthy, connected, syncing)."""
    from app.intelligence_packs.shared.auth_mode import connector_type_lookup_keys

    usable = sorted(ACTIVE_CONNECTOR_STATUSES)
    for type_key in connector_type_lookup_keys(connector_type):
        for env in connector_environment_candidates(environment_name):
            r = (
                client.table("connectors")
                .select("id, org_id, type, status, config, environment, created_at, updated_at")
                .eq("org_id", org_id)
                .eq("environment", env)
                .eq("type", type_key)
                .in_("status", usable)
                .is_("deleted_at", "null")
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
            )
            if r.data:
                return dict(r.data[0])
    return None


def get_connector(
    client: Client,
    org_id: str,
    connector_id: str,
    environment_name: str = "production",
) -> dict | None:
    """Get connector by id. No secrets."""
    for env in connector_environment_candidates(environment_name):
        r = (
            client.table("connectors")
            .select("id, org_id, type, status, config, environment, created_at, updated_at")
            .eq("id", connector_id)
            .eq("org_id", org_id)
            .eq("environment", env)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        if r.data:
            return dict(r.data[0])
    return None


def create_connector(
    client: Client,
    org_id: str,
    connector_type: str,
    config: dict,
    created_by: str | None,
    environment_name: str = "production",
    *,
    status: str = "active",
) -> dict:
    """Create connector. Returns row without secrets.

    Pass status=\"needs_connection\" for marketplace template stubs (no auth yet).
    """
    row = {
        "org_id": org_id,
        "type": connector_type,
        "vendor": connector_type,
        "status": status or "active",
        "config": config or {},
        "created_by": created_by,
        "environment": normalize_environment_name(environment_name),
    }
    r = client.table("connectors").insert(row).execute()
    if not r.data or len(r.data) == 0:
        raise RuntimeError("connectors insert returned no row")
    out = dict(r.data[0])
    out.pop("encrypted_value", None)
    return out


def update_connector(
    client: Client,
    org_id: str,
    connector_id: str,
    config: dict | None,
    status: str | None,
    environment_name: str = "production",
) -> dict | None:
    """Update connector. Returns updated row without secrets."""
    payload = {}
    if config is not None:
        payload["config"] = config
    if status is not None:
        payload["status"] = status
    if not payload:
        return get_connector(client, org_id, connector_id, environment_name=environment_name)
    r = (
        client.table("connectors")
        .update(payload)
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .execute()
    )
    if not r.data or len(r.data) == 0:
        return None
    return dict(r.data[0])


def set_secret(
    client: Client,
    org_id: str,
    connector_id: str,
    key_name: str,
    plaintext_value: str,
    settings: Settings,
) -> None:
    """Upsert secret. Encrypted at rest."""
    org_region = _org_residency(client, org_id)
    connector_region = _connector_data_region(client, org_id, connector_id)
    enforce_region_for_connector_tokens(org_region, connector_region)
    if connector_region is None:
        connector = (
            client.table("connectors")
            .select("config")
            .eq("org_id", org_id)
            .eq("id", connector_id)
            .limit(1)
            .execute()
        )
        if connector.data:
            config = safe_normalize_stored_dict(connector.data[0], key="config")
            config["dataRegion"] = org_region
            client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()
    enc = encrypt_secret(plaintext_value, settings.connector_secrets_encryption_key)
    existing = (
        client.table("connector_secrets")
        .select("id")
        .eq("connector_id", connector_id)
        .eq("key_name", key_name)
        .limit(1)
        .execute()
    )
    if existing.data and len(existing.data) > 0:
        client.table("connector_secrets").update({"encrypted_value": enc}).eq("id", existing.data[0]["id"]).execute()
    else:
        client.table("connector_secrets").insert({
            "org_id": org_id,
            "connector_id": connector_id,
            "key_name": key_name,
            "encrypted_value": enc,
        }).execute()


def get_decrypted_secret(
    client: Client,
    connector_id: str,
    key_name: str,
    settings: Settings,
) -> str | None:
    """Decrypt and return secret. Backend-only; never expose to API response."""
    r = (
        client.table("connector_secrets")
        .select("encrypted_value")
        .eq("connector_id", connector_id)
        .eq("key_name", key_name)
        .limit(1)
        .execute()
    )
    if not r.data or len(r.data) == 0:
        return None
    try:
        return decrypt_secret(r.data[0]["encrypted_value"], settings.connector_secrets_encryption_key)
    except ValueError:
        return None
