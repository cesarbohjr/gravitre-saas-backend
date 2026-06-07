"""One-time OAuth state consumption (callback replay protection)."""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_used_jtis: dict[str, float] = {}
_DEFAULT_TTL_SEC = 900


def _prune(now: float) -> None:
    expired = [jti for jti, exp in _used_jtis.items() if exp <= now]
    for jti in expired:
        _used_jtis.pop(jti, None)


def consume_oauth_state_jti(jti: str, *, ttl_seconds: int = _DEFAULT_TTL_SEC) -> None:
    """Mark a state jti as used; raises ValueError if replayed."""
    if not jti:
        raise ValueError("OAuth state missing jti")
    now = time.time()
    with _lock:
        _prune(now)
        if jti in _used_jtis:
            raise ValueError("OAuth state already used")
        _used_jtis[jti] = now + ttl_seconds


def reset_oauth_state_store_for_tests() -> None:
    with _lock:
        _used_jtis.clear()
