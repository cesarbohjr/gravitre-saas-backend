"""Single cache layer for the Gravitre Intelligence Engine (embeddings, retrieval, Tier 0).

Uses REDIS_URL when configured (same redis-py stack as queue/circuit breaker).
Falls back to in-process TTL memory when Redis is unavailable.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.redis_client import get_redis_client

logger = get_logger(__name__)

_MEMORY: dict[str, tuple[float, str]] = {}
_MEMORY_STATS: dict[str, dict[str, int]] = {}


def _digest(*parts: str) -> str:
    raw = ":".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class CacheService:
    """Org-scoped cache with namespace isolation."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._redis = get_redis_client(self.settings)

    def _key(self, namespace: str, *parts: str) -> str:
        return f"gie:{namespace}:{_digest(*parts)}"

    def _record(self, namespace: str, *, hit: bool) -> None:
        bucket = _MEMORY_STATS.setdefault(namespace, {"hit": 0, "miss": 0})
        bucket["hit" if hit else "miss"] += 1
        if self._redis:
            try:
                field = "hit" if hit else "miss"
                self._redis.hincrby(f"gie:stats:{namespace}", field, 1)
            except Exception:  # noqa: BLE001
                pass

    async def record_hit(self, namespace: str) -> None:
        self._record(namespace, hit=True)

    async def record_miss(self, namespace: str) -> None:
        self._record(namespace, hit=False)

    async def record_event(self, namespace: str, field: str = "count", amount: int = 1) -> None:
        bucket = _MEMORY_STATS.setdefault(namespace, {"hit": 0, "miss": 0})
        bucket[field] = int(bucket.get(field) or 0) + amount
        if self._redis:
            try:
                self._redis.hincrby(f"gie:stats:{namespace}", field, amount)
            except Exception:  # noqa: BLE001
                pass

    def get_sync(self, namespace: str, *parts: str) -> Any | None:
        key = self._key(namespace, *parts)
        if self._redis:
            try:
                raw = self._redis.get(key)
                if raw:
                    self._record(namespace, hit=True)
                    return json.loads(raw)
                self._record(namespace, hit=False)
            except Exception as exc:  # noqa: BLE001
                logger.debug("cache redis get failed namespace=%s error=%s", namespace, exc)
        now = time.time()
        entry = _MEMORY.get(key)
        if entry and entry[0] > now:
            self._record(namespace, hit=True)
            return json.loads(entry[1])
        if entry:
            _MEMORY.pop(key, None)
        self._record(namespace, hit=False)
        return None

    def set_sync(self, namespace: str, value: Any, ttl_seconds: int, *parts: str) -> None:
        key = self._key(namespace, *parts)
        payload = json.dumps(value, default=str)
        if self._redis:
            try:
                self._redis.setex(key, max(1, int(ttl_seconds)), payload)
                return
            except Exception as exc:  # noqa: BLE001
                logger.debug("cache redis set failed namespace=%s error=%s", namespace, exc)
        _MEMORY[key] = (time.time() + max(1, ttl_seconds), payload)

    async def get(self, namespace: str, *parts: str) -> Any | None:
        return self.get_sync(namespace, *parts)

    async def set(self, namespace: str, value: Any, ttl_seconds: int, *parts: str) -> None:
        self.set_sync(namespace, value, ttl_seconds, *parts)

    def stats(self, namespace: str) -> dict[str, int]:
        if self._redis:
            try:
                raw = self._redis.hgetall(f"gie:stats:{namespace}") or {}
                if raw:
                    return {str(key): int(value) for key, value in raw.items()}
            except Exception:  # noqa: BLE001
                pass
        return {str(k): int(v) for k, v in _MEMORY_STATS.get(namespace, {"hit": 0, "miss": 0}).items()}


_cache: CacheService | None = None


def get_cache_service(settings: Settings | None = None) -> CacheService:
    global _cache
    if settings is not None:
        return CacheService(settings)
    if _cache is None:
        _cache = CacheService()
    return _cache
