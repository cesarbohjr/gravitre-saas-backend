"""Activate gravitree_managed connector stubs without tenant secrets."""
from __future__ import annotations

import os
from typing import Any

from app.config import Settings
from app.intelligence_packs.shared.auth_mode import (
    AuthMode,
    GRAVITREE_ENV_KEYS,
    get_auth_mode,
    resolve_credential_source,
)
from app.core.safe_dict import safe_normalize_stored_dict


def _platform_env_present(vendor: str, settings: Settings) -> bool:
    keys = GRAVITREE_ENV_KEYS.get(vendor, ())
    if not keys:
        return True
    for key in keys:
        if (os.environ.get(key) or "").strip():
            return True
        # Settings snake_case fallback
        attr = key.lower()
        if bool(getattr(settings, attr, None) or getattr(settings, key.lower().replace("_api_key", "_api_key"), None)):
            # try common settings field names
            pass
    # Named settings fields used by Phase 1 clients
    if vendor == "fred":
        return bool((os.environ.get("FRED_API_KEY") or getattr(settings, "fred_api_key", "") or "").strip())
    if vendor == "nvd":
        return True
    if vendor == "cisa_kev":
        return True
    if vendor == "sec_edgar":
        ua = (os.environ.get("SEC_USER_AGENT") or getattr(settings, "sec_user_agent", "") or "").strip()
        return "@" in ua
    if vendor == "world_bank":
        return True
    if not keys:
        return True
    for key in keys:
        settings_attr = key.lower()
        if (os.environ.get(key) or getattr(settings, settings_attr, "") or "").strip():
            return True
    return False


def activate_gravitree_connector(
    client: Any,
    *,
    org_id: str,
    connector_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Flip needs_connection → active for gravitree_managed when platform creds OK."""
    row = (
        client.table("connectors")
        .select("id, org_id, type, status, config, deleted_at")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    rows = row.data or []
    if not rows:
        raise ValueError("Connector not found")
    conn = rows[0]
    vendor = str(conn.get("type") or "").strip().lower()
    if get_auth_mode(vendor) != AuthMode.GRAVITREE_MANAGED:
        raise PermissionError(f"{vendor} is not gravitree_managed")

    present = _platform_env_present(vendor, settings)
    resolved = resolve_credential_source(
        vendor,
        org_has_secret=False,
        platform_env_present=present,
        settings=settings,
    )
    if not resolved.get("ok"):
        raise RuntimeError(str(resolved.get("message") or f"{vendor} platform credentials unavailable"))

    config = safe_normalize_stored_dict(conn, key="config")
    config["auth_mode"] = AuthMode.GRAVITREE_MANAGED.value
    config["activated_via"] = "activate_gravitree_connector"
    client.table("connectors").update({"status": "active", "config": config}).eq("id", connector_id).eq(
        "org_id", org_id
    ).execute()
    return {
        "id": connector_id,
        "type": vendor,
        "status": "active",
        "authMode": AuthMode.GRAVITREE_MANAGED.value,
    }
