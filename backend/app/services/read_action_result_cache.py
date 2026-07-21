"""TTL cache for read-only connector invoke results (shared across users in org)."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_TTL_SECONDS = 90
_MAX_ENTRIES = 512
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

_READ_ACTION_MARKERS = (
    ".list",
    ".get",
    ".search",
    ".query",
    ".read",
    ".fetch",
)


def is_read_invoke_action(invoke_action: str) -> bool:
    action = str(invoke_action or "").strip().lower()
    if not action:
        return False
    from app.services.connected_files_service import is_permission_sensitive_file_action

    if is_permission_sensitive_file_action(action):
        return False
    if any(marker in action for marker in (".create", ".update", ".delete", ".send", ".post", ".write")):
        return False
    return any(action.endswith(marker) or marker in action for marker in _READ_ACTION_MARKERS)


def _cache_key(org_id: str, invoke_action: str, params: dict[str, Any]) -> str:
    payload = json.dumps(params or {}, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{org_id}:{invoke_action}:{digest}"


def get_cached_read_result(
    org_id: str,
    invoke_action: str,
    params: dict[str, Any],
) -> dict[str, Any] | None:
    key = _cache_key(org_id, invoke_action, params)
    row = _CACHE.get(key)
    if not row:
        return None
    expires_at, payload = row
    if time.time() > expires_at:
        _CACHE.pop(key, None)
        return None
    return dict(payload)


def set_cached_read_result(
    org_id: str,
    invoke_action: str,
    params: dict[str, Any],
    result: dict[str, Any],
    *,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> None:
    if len(_CACHE) >= _MAX_ENTRIES:
        oldest = min(_CACHE.items(), key=lambda item: item[1][0])[0]
        _CACHE.pop(oldest, None)
    key = _cache_key(org_id, invoke_action, params)
    _CACHE[key] = (time.time() + max(5, ttl_seconds), dict(result))


def clear_read_action_result_cache() -> None:
    _CACHE.clear()
