"""Short-TTL cache for connected integration snapshots (agent platform perf)."""
from __future__ import annotations

import time
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_TTL_SECONDS = 45
_CACHE: dict[str, tuple[float, list[str]]] = {}


def _cache_key(org_id: str, environment_name: str) -> str:
    return f"{org_id}:{environment_name or 'production'}"


def get_cached_connected(org_id: str, environment_name: str = "production") -> list[str] | None:
    key = _cache_key(org_id, environment_name)
    row = _CACHE.get(key)
    if not row:
        return None
    expires_at, payload = row
    if time.time() > expires_at:
        _CACHE.pop(key, None)
        return None
    return list(payload)


def set_cached_connected(
    org_id: str,
    connected: list[str],
    *,
    environment_name: str = "production",
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> list[str]:
    key = _cache_key(org_id, environment_name)
    _CACHE[key] = (time.time() + max(5, ttl_seconds), list(connected))
    return list(connected)


def clear_connector_snapshot_cache() -> None:
    _CACHE.clear()


def list_connected_integrations_cached(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
    force_live: bool = True,
    action_key: str | None = None,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> list[str]:
    """Cached wrapper around connector availability listing."""
    if not force_live:
        cached = get_cached_connected(org_id, environment_name)
        if cached is not None:
            return cached
    from app.connectors.connector_availability_service import list_executable_integrations
    from app.config import get_settings

    connected = list_executable_integrations(
        client,
        org_id,
        get_settings(),
        environment_name=environment_name,
        force_live=force_live,
        action_key=action_key,
    )
    return set_cached_connected(
        org_id,
        connected,
        environment_name=environment_name,
        ttl_seconds=ttl_seconds,
    )


def prefetch_connected_integrations(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
) -> None:
    """Best-effort warm cache; safe to call fire-and-forget."""
    try:
        list_connected_integrations_cached(
            client,
            org_id,
            environment_name=environment_name,
            force_live=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("connector_prefetch_skipped org_id=%s err=%s", org_id, exc)
