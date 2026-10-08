"""Small thread-safe TTL cache with tag-based invalidation.

Used for short-lived read-through caches of computed per-org responses
(/api/billing/status, /api/entitlements, /api/auth/me). Design points:

- Bounded: at most ``max_entries`` live entries; the least recently written
  entry is evicted first, expired entries are dropped on access.
- Monotonic clock, so wall-clock jumps never extend or shorten a TTL.
- Values are deep-copied on the way in and on the way out, so neither the
  producer nor any caller can mutate what other requests will read.
- Entries carry tags (e.g. ``("org", org_id)``) and ``invalidate_tag`` drops
  every entry carrying that tag.
- Writes race-safely with invalidation: callers take ``token()`` before
  computing a value and pass it to ``set``; if any invalidation happened in
  between, the (possibly stale) value is not stored.
"""
from __future__ import annotations

import copy
import os
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable, Iterable
from typing import Any

_MISSING = object()


class TTLCache:
    def __init__(
        self,
        ttl_seconds: float,
        *,
        max_entries: int = 2048,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self.ttl_seconds = float(ttl_seconds)
        self.max_entries = int(max_entries)
        self._clock = clock
        self._lock = threading.Lock()
        # key -> (expires_at, value, tags)
        self._entries: OrderedDict[Hashable, tuple[float, Any, frozenset[Hashable]]] = OrderedDict()
        self._epoch = 0

    @property
    def enabled(self) -> bool:
        return self.ttl_seconds > 0

    def token(self) -> int:
        """Invalidation epoch to pass to ``set`` (see module docstring)."""
        with self._lock:
            return self._epoch

    def get(self, key: Hashable, default: Any = None) -> Any:
        if not self.enabled:
            return default
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return default
            expires_at, value, _tags = entry
            if expires_at <= self._clock():
                del self._entries[key]
                return default
        return copy.deepcopy(value)

    def set(
        self,
        key: Hashable,
        value: Any,
        *,
        tags: Iterable[Hashable] = (),
        token: int | None = None,
        ttl_seconds: float | None = None,
    ) -> bool:
        """Store ``value``; returns False when skipped (disabled or invalidated since ``token``)."""
        ttl = self.ttl_seconds if ttl_seconds is None else float(ttl_seconds)
        if ttl <= 0:
            return False
        stored = copy.deepcopy(value)
        with self._lock:
            if token is not None and token != self._epoch:
                return False
            now = self._clock()
            self._entries.pop(key, None)
            self._entries[key] = (now + ttl, stored, frozenset(tags))
            if len(self._entries) > self.max_entries:
                self._purge_expired_locked(now)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
        return True

    def invalidate(self, key: Hashable) -> None:
        with self._lock:
            self._epoch += 1
            self._entries.pop(key, None)

    def invalidate_tag(self, tag: Hashable) -> int:
        with self._lock:
            self._epoch += 1
            doomed = [k for k, (_exp, _val, tags) in self._entries.items() if tag in tags]
            for k in doomed:
                del self._entries[k]
            return len(doomed)

    def clear(self) -> None:
        with self._lock:
            self._epoch += 1
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            self._purge_expired_locked(self._clock())
            return len(self._entries)

    def _purge_expired_locked(self, now: float) -> None:
        expired = [k for k, (exp, _val, _tags) in self._entries.items() if exp <= now]
        for k in expired:
            del self._entries[k]


def ttl_from_env(name: str, default: float) -> float:
    """Read a TTL (seconds) from the environment; invalid values fall back to ``default``."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return max(0.0, float(raw))
    except ValueError:
        return default
