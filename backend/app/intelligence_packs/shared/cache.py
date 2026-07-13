"""In-memory TTL cache for gravitree-managed intelligence sources (Phase 1)."""
from __future__ import annotations

import time
from threading import Lock
from typing import Any


class SourceCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            row = self._store.get(key)
            if not row:
                return None
            expires_at, value = row
            if time.time() >= expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, *, ttl_seconds: int) -> None:
        with self._lock:
            self._store[key] = (time.time() + max(1, ttl_seconds), value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_SOURCE_CACHE = SourceCache()


def get_source_cache() -> SourceCache:
    return _SOURCE_CACHE
