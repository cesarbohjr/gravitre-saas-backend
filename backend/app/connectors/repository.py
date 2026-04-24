"""IN-00: Connector CRUD and secrets. Never return secrets to callers."""
from __future__ import annotations

from supabase import Client

from app.connectors.crypto import decrypt_secret, encrypt_secret
from app.config import Settings


def list_connectors(client: Client, org_id: str, environment_name: str = "default") -> list[dict]:
    """List connectors for org. No secrets."""
    r = (
        client.table("connectors")
        .select("id, org_id, type, status, config, environment, created_at, updated_at")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .order("created_at", desc=True)
        .execute()
    )
    return [dict(row) for row in (r.data or [])]


def get_connector_by_type(
    client: Client,
    org_id: str,
    connector_type: str,
    environment_name: str = "default",
) -> dict | None:
    """Get first active connector of type for org."""
    r = (
        client.table("connectors")
        .select("id, org_id, type, status, config, environment, created_at, updated_at")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("type", connector_type)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if not r.data or len(r.data) == 0:
        return None
    return dict(r.data[0])


def get_connector(
    client: Client,
    org_id: str,
    connector_id: str,
    environment_name: str = "default",
) -> dict | None:
    """Get connector by id. No secrets."""
    r = (
        client.table("connectors")
        .select("id, org_id, type, status, config, environment, created_at, updated_at")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .limit(1)
        .execute()
    )
    if not r.data or len(r.data) == 0:
        return None
    return dict(r.data[0])


def create_connector(
    client: Client,
    org_id: str,
    connector_type: str,
    config: dict,
    created_by: str | None,
    environment_name: str = "default",
) -> dict:
    """Create connector. Returns row without secrets."""
    row = {
        "org_id": org_id,
        "type": connector_type,
        "status": "active",
        "config": config or {},
        "created_by": created_by,
        "environment": environment_name,
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
    environment_name: str = "default",
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
        .eq("environment", environment_name)
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
