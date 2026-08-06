"""API rate limiting — Redis-backed with in-process fallback."""
from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Any

from fastapi import HTTPException, Request, status

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_WINDOW_S = 60


class _SlidingWindow:
    def __init__(self, window_seconds: float = 60.0) -> None:
        self._window = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = Lock()

    def hit(self, key: str, limit: int) -> tuple[bool, int]:
        if limit <= 0:
            return True, limit
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            bucket = self._events.setdefault(key, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False, 0
            bucket.append(now)
            return True, max(0, limit - len(bucket))


_memory = _SlidingWindow()


def _redis_hit(client: Any, redis_key: str, limit: int, window_s: int) -> tuple[bool, int, int | None]:
    bucket = int(time.time() // window_s)
    key = f"{redis_key}:{bucket}"
    count = int(client.incr(key))
    if count == 1:
        client.expire(key, window_s + 1)
    remaining = max(0, limit - count)
    if count > limit:
        retry_after = window_s - (int(time.time()) % window_s)
        return False, 0, retry_after
    return True, remaining, None


class RateLimiter:
    """Sliding/fixed-window limiter with Redis when available."""

    async def check(
        self,
        identifier: str,
        limit: int,
        window_seconds: int = 60,
    ) -> dict[str, Any]:
        if limit <= 0:
            return {"allowed": True, "remaining": limit, "retry_after": None}

        from app.core.redis_client import get_sync_redis

        settings = get_settings()
        client = get_sync_redis(settings)
        if client is not None:
            try:
                allowed, remaining, retry_after = _redis_hit(
                    client,
                    f"api:rl:{identifier}",
                    limit,
                    window_seconds,
                )
                return {
                    "allowed": allowed,
                    "remaining": remaining,
                    "retry_after": retry_after,
                }
            except Exception as exc:  # noqa: BLE001
                logger.debug("rate_limit redis fallback identifier=%s error=%s", identifier, exc)

        allowed, remaining = _memory.hit(identifier, limit)
        retry_after = window_seconds if not allowed else None
        return {"allowed": allowed, "remaining": remaining, "retry_after": retry_after}


_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _org_or_ip(request: Request) -> str:
    org = (request.headers.get("x-org-id") or "").strip()
    if org:
        return f"org:{org}"
    return f"ip:{_client_ip(request)}"


async def enforce_rate_limit(
    request: Request,
    *,
    endpoint: str,
    limit: int,
    window: int = 60,
) -> None:
    identifier = f"{endpoint}:{_org_or_ip(request)}"
    result = await get_rate_limiter().check(identifier, limit, window)
    if result["allowed"]:
        return
    retry_after = int(result.get("retry_after") or window)
    from app.core.metrics import log_business_event

    log_business_event("rate_limit_exceeded", endpoint=endpoint, identifier=identifier)
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again shortly.",
            "retry_after": retry_after,
        },
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": "0",
        },
    )


# (method, path_prefix, limit_per_minute)
# method "*" matches any HTTP method (needed for OAuth GET callbacks + webhooks).
SENSITIVE_RATE_LIMITS: tuple[tuple[str, str, int], ...] = (
    ("POST", "/api/auth", 10),
    ("POST", "/api/intelligence-engine", 60),
    ("POST", "/api/agent-jobs", 30),
    ("POST", "/api/marketplace", 10),
    ("POST", "/api/admin/mcp", 5),
    ("*", "/api/connectors/oauth", 60),
    ("*", "/api/webhooks", 120),
)
