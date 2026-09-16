"""Cooperative cancel for governed chat streams (Phase F1).

Stop is conversation-scoped. Redis coordinates across workers; when Redis is
unavailable the flag lives in-process (single worker only).
"""
from __future__ import annotations

import threading
import time
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.redis_client import get_redis_client

logger = get_logger(__name__)

STOP_TTL_SECONDS = 120
_KEY_PREFIX = "chat:stop:"

_lock = threading.Lock()
_local_stops: dict[str, float] = {}


def stop_key(org_id: str, conversation_id: str) -> str:
    return f"{_KEY_PREFIX}{org_id}:{conversation_id}"


def _prune_local(now: float) -> None:
    expired = [key for key, until in _local_stops.items() if until <= now]
    for key in expired:
        _local_stops.pop(key, None)


def request_stop(
    org_id: str,
    conversation_id: str,
    *,
    settings: Settings | None = None,
) -> bool:
    """Mark the active turn for this conversation as cancelled. Returns True if stored."""
    oid = (org_id or "").strip()
    cid = (conversation_id or "").strip()
    if not oid or not cid:
        return False
    key = stop_key(oid, cid)
    redis = get_redis_client(settings or get_settings())
    if redis is not None:
        try:
            redis.setex(key, STOP_TTL_SECONDS, "1")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat stop redis setex failed key=%s error=%s", key, str(exc)[:200])
    with _lock:
        _local_stops[key] = time.monotonic() + STOP_TTL_SECONDS
    return True


def is_stop_requested(
    org_id: str,
    conversation_id: str | None,
    *,
    settings: Settings | None = None,
) -> bool:
    oid = (org_id or "").strip()
    cid = (conversation_id or "").strip() if conversation_id else ""
    if not oid or not cid:
        return False
    key = stop_key(oid, cid)
    redis = get_redis_client(settings or get_settings())
    if redis is not None:
        try:
            return bool(redis.get(key))
        except Exception as exc:  # noqa: BLE001
            logger.debug("chat stop redis get failed key=%s error=%s", key, str(exc)[:200])
    now = time.monotonic()
    with _lock:
        _prune_local(now)
        until = _local_stops.get(key)
        return bool(until and until > now)


def clear_stop(
    org_id: str,
    conversation_id: str | None,
    *,
    settings: Settings | None = None,
) -> None:
    oid = (org_id or "").strip()
    cid = (conversation_id or "").strip() if conversation_id else ""
    if not oid or not cid:
        return
    key = stop_key(oid, cid)
    redis = get_redis_client(settings or get_settings())
    if redis is not None:
        try:
            redis.delete(key)
        except Exception as exc:  # noqa: BLE001
            logger.debug("chat stop redis delete failed key=%s error=%s", key, str(exc)[:200])
    with _lock:
        _local_stops.pop(key, None)


def reset_local_stops_for_tests() -> None:
    with _lock:
        _local_stops.clear()


async def stream_should_stop(
    http_request: Any | None,
    org_id: str,
    conversation_id: str | None,
    *,
    settings: Settings | None = None,
) -> bool:
    if is_stop_requested(org_id, conversation_id, settings=settings):
        return True
    if http_request is None:
        return False
    try:
        disconnected = http_request.is_disconnected
        if callable(disconnected):
            result = disconnected()
            if hasattr(result, "__await__"):
                return bool(await result)
            return bool(result)
    except Exception:  # noqa: BLE001
        return False
    return False
