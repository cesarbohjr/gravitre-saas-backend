"""Segment connector credential helper — write key via api_key secret (STA-67)."""
from __future__ import annotations

from typing import Any

from app.config import Settings
from app.connectors.platform import masked_api_key_for_response, store_connector_api_key
from app.core.safe_dict import safe_normalize_stored_dict


def normalize_vendor(vendor: str) -> str:
    key = vendor.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if key in {"segment", "segmentio"}:
        return "segment"
    return key


def store_segment_write_key(
    client: Any,
    org_id: str,
    connector_id: str,
    write_key: str,
    settings: Settings,
) -> None:
    """Persist Segment source write key using platform api_key storage."""
    store_connector_api_key(client, org_id, connector_id, write_key.strip(), settings)
    row = (
        client.table("connectors")
        .select("config")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    config = safe_normalize_stored_dict((row.data or [{}])[0], key="config")
    config["auth_type"] = "api_key"
    config["segment_write_key_configured"] = True
    client.table("connectors").update(
        {
            "config": config,
            "status": "active",
        }
    ).eq("id", connector_id).eq("org_id", org_id).execute()


def segment_connection_status(
    client: Any,
    connector_id: str,
    row: dict[str, Any],
    settings: Settings,
) -> str:
    masked = masked_api_key_for_response(client, connector_id, row, settings)
    if masked:
        return "connected"
    return "pending_auth"
