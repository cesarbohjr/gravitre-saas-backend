"""Atomic marketplace asset counter increments (MKT-10.1)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

logger = logging.getLogger(__name__)

MarketplaceCounter = Literal["install_count", "clone_count"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_missing_rpc_error(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "increment_marketplace_asset_counter" in message
        or ("function" in message and "does not exist" in message)
        or "pgrst202" in message
    )


def _legacy_increment(client: Any, asset_id: str, counter: MarketplaceCounter) -> int:
    """Read-modify-write fallback when RPC migration is not applied yet."""
    result = (
        client.table("marketplace_assets")
        .select(counter)
        .eq("id", asset_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise ValueError(f"Marketplace asset not found: {asset_id}")
    current = int(result.data[0].get(counter) or 0)
    next_value = current + 1
    client.table("marketplace_assets").update(
        {counter: next_value, "updated_at": _now()}
    ).eq("id", asset_id).execute()
    logger.warning(
        "marketplace_counter_legacy_increment asset_id=%s counter=%s",
        asset_id,
        counter,
    )
    return next_value


def increment_marketplace_counter(
    client: Any,
    asset_id: str,
    counter: MarketplaceCounter,
) -> int:
    """Atomically increment ``install_count`` or ``clone_count`` via Postgres RPC."""
    try:
        result = client.rpc(
            "increment_marketplace_asset_counter",
            {"p_asset_id": asset_id, "p_counter": counter},
        ).execute()
    except Exception as exc:
        if _is_missing_rpc_error(exc):
            return _legacy_increment(client, asset_id, counter)
        raise

    data = result.data
    if isinstance(data, list) and data:
        return int(data[0])
    if isinstance(data, int):
        return data
    return int(data or 0)
