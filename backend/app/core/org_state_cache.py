"""Short-TTL response caches for per-org page-load reads, plus invalidation.

/api/billing/status, /api/entitlements and /api/auth/me run on every page load
and each used to cost ~1s of sequential Supabase round trips. Their computed
responses are cached here for ``ORG_STATE_CACHE_TTL_SECONDS`` (default 30s;
0 disables) — only when the request uses the process-wide production client
(``app.core.db.is_shared_service_client``), so tests that patch
``create_client`` or pass mock clients are never cached.

Every write path that changes billing, plan, entitlement, membership, org or
profile state must call ``invalidate_org_state(org_id)`` and/or
``invalidate_user_state(user_id)``. Both also drop the billing gate's
"allowed" decisions for that org/user (app/middleware/billing_gate.py).
Invalidation never raises: a cache bug must not fail a write.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.core.logging import get_logger
from app.core.ttl_cache import TTLCache, ttl_from_env

logger = get_logger(__name__)

TTL_ENV_VAR = "ORG_STATE_CACHE_TTL_SECONDS"
DEFAULT_TTL_SECONDS = 30.0

_ttl = ttl_from_env(TTL_ENV_VAR, DEFAULT_TTL_SECONDS)

# (org_id, environment) -> /api/billing/status payload
billing_status_cache = TTLCache(_ttl, max_entries=4096)
# (org_id,) -> resolve_entitlements() payload
entitlements_cache = TTLCache(_ttl, max_entries=4096)
# (user_id, org_id, email) -> /api/auth/me payload
auth_me_cache = TTLCache(_ttl, max_entries=8192)

_ALL_CACHES = (billing_status_cache, entitlements_cache, auth_me_cache)


def org_tag(org_id: str | None) -> tuple[str, str]:
    return ("org", str(org_id or ""))


def user_tag(user_id: str | None) -> tuple[str, str]:
    return ("user", str(user_id or ""))


def cache_allowed(client: Any) -> bool:
    """Cache only for the shared production service-role client."""
    from app.core.db import is_shared_service_client

    try:
        return is_shared_service_client(client)
    except Exception:  # noqa: BLE001
        return False


def invalidate_org_state(*org_ids: str | None) -> None:
    """Drop every cached response (and billing-gate decision) for these orgs."""
    for org_id in org_ids:
        oid = str(org_id or "").strip()
        if not oid:
            continue
        try:
            tag = org_tag(oid)
            for cache in _ALL_CACHES:
                cache.invalidate_tag(tag)
            from app.middleware.billing_gate import forget_org

            forget_org(oid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("org_state_cache invalidate_org failed org_id=%s error=%s", oid, exc)


def invalidate_user_state(*user_ids: str | None) -> None:
    """Drop cached /me payloads (and billing-gate decisions) for these users."""
    for user_id in user_ids:
        uid = str(user_id or "").strip()
        if not uid:
            continue
        try:
            tag = user_tag(uid)
            for cache in _ALL_CACHES:
                cache.invalidate_tag(tag)
            from app.middleware.billing_gate import forget_user

            forget_user(uid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("org_state_cache invalidate_user failed user_id=%s error=%s", uid, exc)


def invalidate_org_and_users(org_id: str | None, user_ids: Iterable[str | None] = ()) -> None:
    invalidate_org_state(org_id)
    invalidate_user_state(*list(user_ids))


def clear_org_state_caches() -> None:
    """Drop everything (tests, or a bulk change with no single org)."""
    for cache in _ALL_CACHES:
        cache.clear()
    try:
        from app.middleware.billing_gate import forget_all

        forget_all()
    except Exception:  # noqa: BLE001
        pass
