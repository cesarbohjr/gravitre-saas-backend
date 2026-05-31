"""Shared sync Redis client for cross-instance coordination (rate limiter,
circuit breaker). Returns None when REDIS_URL is unset or Redis is unreachable,
so all callers degrade gracefully to in-process behavior.

Sync (not asyncio) on purpose: the guardrail chokepoint already does brief sync
I/O (the budget gate queries Supabase synchronously), and these ops are single
fast commands. Clients are cached per-URL; a URL that fails to connect once is
remembered so we don't re-ping on every call.
"""
from __future__ import annotations

from typing import Any

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_clients: dict[str, Any] = {}
_failed: set[str] = set()


def get_sync_redis(settings: Settings) -> Any | None:
    url = (getattr(settings, "redis_url", "") or "").strip()
    if not url or url in _failed:
        return None
    if url in _clients:
        return _clients[url]
    try:
        import redis  # redis-py (sync)

        client = redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
        client.ping()
        _clients[url] = client
        logger.info("redis connected for cross-instance coordination")
        return client
    except Exception as exc:  # noqa: BLE001
        logger.warning("redis unavailable, using in-process fallback: %s", str(exc))
        _failed.add(url)
        return None


def get_redis_client(settings: Settings | None = None) -> Any | None:
    """Return the shared sync Redis client, or None when unavailable."""
    from app.config import get_settings

    return get_sync_redis(settings or get_settings())
