"""BE-00: Auth and org context. Supabase Auth (email + magic link); org from DB (single-org-per-user)."""
import asyncio
import time
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Header, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.auth.jwt_verify import decode_supabase_jwt
from app.connectors.constants import normalize_environment_name
from app.auth.platform_admin import (
    can_trigger_knowledge_sync,
    is_org_admin_role,
    is_org_member_role,
    is_platform_admin,
)
from app.config import Settings, get_settings
from app.core.logging import get_logger, org_id_ctx, user_id_ctx

security = HTTPBearer(auto_error=False)
logger = get_logger(__name__)

# key -> Client, lazy singleton per (url, service_role_key) pair.
#
# Perf fix (2026-09-07): every dependency in this module previously called
# `create_client(...)` fresh on every single request (confirmed: 4 separate
# call sites — get_org_context, require_admin, require_org_member,
# require_platform_admin — each constructing a brand-new httpx-backed
# Supabase client, with its own connection pool, per call, with zero
# connection reuse across requests). Reusing one client per (url, key) pair
# is safe: supabase-py's sync Client wraps httpx.Client, which is documented
# as thread-safe for concurrent use, and the credentials/URL are static for
# the life of the process. Same pattern as the AsyncAnthropic client-reuse
# fix in app/services/providers/anthropic_adapter.py.
_service_client_cache: dict[tuple[str, str], Client] = {}


def _get_cached_service_client(settings: Settings) -> Client:
    # Local (not module-level) import deliberately preserved: tests patch
    # `supabase.create_client` directly (`patch("supabase.create_client", ...)`)
    # and rely on that attribute lookup happening at call time, not at this
    # module's import time — an eager top-level `from supabase import
    # create_client` would bind the *original* function before any patch
    # applies and silently defeat those tests. Because the result is cached
    # below, this import (and the real `create_client` call) still only
    # happens once per (url, key) pair in production.
    from supabase import create_client

    key = (settings.supabase_url, settings.supabase_service_role_key)
    client = _service_client_cache.get(key)
    if client is None:
        client = create_client(*key)
        _service_client_cache[key] = client
    return client


def clear_cached_service_client() -> None:
    """Test-only escape hatch so patched `create_client` mocks aren't stuck cached."""
    _service_client_cache.clear()


# 401 reason categories for logging (never log raw tokens)
REASON_MISSING_TOKEN = "missing_token"
REASON_INVALID_SIGNATURE = "invalid_signature"
REASON_EXPIRED = "expired"
REASON_INVALID_CLAIMS = "invalid_claims"


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Strict auth only: validate Supabase JWT (iss, aud, leeway). Raises 401 if missing or invalid."""
    if not credentials:
        logger.warning("401 auth_failure reason=%s", REASON_MISSING_TOKEN)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    token = credentials.credentials
    if not token:
        logger.warning("401 auth_failure reason=%s", REASON_MISSING_TOKEN)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    try:
        payload = decode_supabase_jwt(token, settings)
    except jwt.ExpiredSignatureError:
        logger.warning("401 auth_failure reason=%s", REASON_EXPIRED)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    except jwt.InvalidSignatureError:
        logger.warning("401 auth_failure reason=%s", REASON_INVALID_SIGNATURE)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    except jwt.InvalidAudienceError:
        logger.warning("401 auth_failure reason=%s", REASON_INVALID_CLAIMS)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    except jwt.InvalidIssuerError:
        logger.warning("401 auth_failure reason=%s", REASON_INVALID_CLAIMS)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    except jwt.PyJWTError:
        logger.warning("401 auth_failure reason=%s", REASON_INVALID_CLAIMS)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")
    if not user_id:
        logger.warning("401 auth_failure reason=%s", REASON_INVALID_CLAIMS)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user_id_ctx.set(user_id)

    return {
        "user_id": user_id,
        "email": payload.get("email") or None,
    }


class _OrgContextForbidden(Exception):
    """Internal signal: the singleflight-shared resolution determined 403.

    Raised (never HTTPException) inside `_resolve_org_context_live` — see
    that function's docstring for why HTTPException must not cross the
    singleflight boundary directly.
    """


async def _resolve_org_context_live(
    settings: Settings,
    user_id: str,
    requested_org_id: str,
    email: str | None,
) -> str | None:
    """Do the real (network) org-context resolution — no caching, no contextvars.

    Perf fix (2026-09-07): the two independent membership lookups
    (`is_platform_admin`, `list_member_org_ids`) now run concurrently via
    `asyncio.to_thread` instead of sequentially and synchronously on the
    event loop — this alone halves the cold/cache-miss latency and, more
    importantly, stops this call from blocking *other* concurrent requests
    on the same worker for its full network round-trip duration.

    Deliberately does NOT set `org_id_ctx` — this function's result may be
    shared across several concurrent callers via `resolve_singleflight`
    (each running in its own asyncio Task with its own copied contextvar
    context), so only the caller (`get_org_context` itself, once per real
    request) may safely set that contextvar. Raises `_OrgContextForbidden`
    (not `HTTPException`) for the 403 case for the same reason: a shared
    singleflight task's exception is re-raised as-is to every awaiting
    caller, and `get_org_context` translates it back to a real
    `HTTPException(403)` for each of its own individual callers.
    """
    from app.services.org_membership import (
        ensure_user_workspace,
        list_member_org_ids,
        load_user_primary_org_id,
        pick_default_org_id,
    )

    client = _get_cached_service_client(settings)

    platform_admin_task = asyncio.to_thread(is_platform_admin, client, user_id)
    member_org_ids_task = asyncio.to_thread(list_member_org_ids, client, user_id)
    platform_admin, member_org_ids_result = await asyncio.gather(
        platform_admin_task,
        member_org_ids_task,
        return_exceptions=True,
    )
    if isinstance(platform_admin, Exception):
        logger.warning("platform_admin_lookup_failed user_id=%s error=%s", user_id, str(platform_admin))
        platform_admin = False
    if isinstance(member_org_ids_result, Exception):
        logger.warning("org_lookup_failed user_id=%s error=%s", user_id, str(member_org_ids_result))
        member_org_ids: list[str] = []
    else:
        member_org_ids = member_org_ids_result

    if requested_org_id:
        if requested_org_id in member_org_ids or platform_admin:
            return requested_org_id
        # Fail loud — never silently substitute the caller's default org.
        # Shared path: every require_org_member / get_org_context caller benefits.
        logger.warning(
            "org_context_requested_not_member user_id=%s org_id=%s",
            user_id,
            requested_org_id,
        )
        raise _OrgContextForbidden()

    if member_org_ids:
        primary_org_id = await asyncio.to_thread(load_user_primary_org_id, client, user_id)
        org_id = pick_default_org_id(
            member_org_ids,
            primary_org_id=primary_org_id,
            requested_org_id=None,
        )
        if org_id:
            if len(member_org_ids) > 1:
                logger.info(
                    "org_context_multi_org_default user_id=%s org_id=%s membership_count=%s",
                    user_id,
                    org_id,
                    len(member_org_ids),
                )
            return org_id

    org_id = await asyncio.to_thread(ensure_user_workspace, client, user_id, email=email)
    if org_id:
        return org_id

    logger.warning("org_membership_missing user_id=%s", user_id)
    return None


async def get_org_context(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str | None:
    """Resolve org_id from membership rows, optional x-org-id header, or auto-provision.

    Multi-org users are supported (STA-72). When several memberships exist and no
    valid org is requested, the user's primary org (public.users.org_id) or first
    non-demo membership is used. Authenticated users without any membership get a
    personal workspace auto-created so AI chat and core flows remain usable.

    Perf/regression fix (2026-09-07): this dependency resolves on nearly every
    authenticated request, including the voice legacy path's high-frequency
    `/turn-taking/event` endpoint. It previously did two sequential, blocking
    Supabase network calls inline in this `async def` with no `await` —
    confirmed live to serialize a burst of 15 concurrent turn-taking calls
    into a uniform ~2.5s each (see `org_context_cache.py`'s module docstring
    for the full, live-measured evidence). This now checks a short-TTL cache
    first (near-zero cost on a hit — the common case for repeat calls within
    one active voice utterance, which all share the same user_id +
    x-org-id), and de-duplicates concurrent cache-misses via singleflight so
    a cold burst triggers exactly one real resolution, not N.
    """
    from app.auth.org_context_cache import (
        get_cached_org_context,
        resolve_singleflight,
        set_cached_org_context,
    )

    started_at = time.perf_counter()
    user_id = current_user["user_id"]
    requested_org_id = (request.headers.get("x-org-id") or request.query_params.get("org_id") or "").strip()

    cached = get_cached_org_context(user_id, requested_org_id)
    if cached is not None:
        cached_org_id, forbidden = cached
        # Standing latency visibility (2026-09-07): the pre-fix regression had
        # NO instrumentation at all on this dependency — the only evidence of
        # its cost was a browser-side network trace + an ad-hoc live probe.
        # This closes that gap permanently so a future regression here shows
        # up in logs/metrics before a user has to report it.
        logger.info(
            "org_context_resolved user_id=%s cache=hit forbidden=%s elapsed_ms=%s",
            user_id,
            forbidden,
            int((time.perf_counter() - started_at) * 1000),
        )
        if forbidden:
            org_id_ctx.set("")
            logger.warning(
                "org_context_requested_not_member user_id=%s org_id=%s cache=hit",
                user_id,
                requested_org_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of the requested organization",
            )
        org_id_ctx.set(cached_org_id or "")
        return cached_org_id

    singleflight_key = f"{user_id}:{requested_org_id}"

    async def _factory() -> str | None:
        return await _resolve_org_context_live(
            settings, user_id, requested_org_id, current_user.get("email")
        )

    try:
        org_id = await resolve_singleflight(singleflight_key, _factory)
    except _OrgContextForbidden:
        set_cached_org_context(user_id, requested_org_id, org_id=None, forbidden=True)
        org_id_ctx.set("")
        logger.info(
            "org_context_resolved user_id=%s cache=miss forbidden=True elapsed_ms=%s",
            user_id,
            int((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of the requested organization",
        )

    set_cached_org_context(user_id, requested_org_id, org_id=org_id, forbidden=False)
    org_id_ctx.set(org_id or "")
    logger.info(
        "org_context_resolved user_id=%s cache=miss forbidden=False elapsed_ms=%s",
        user_id,
        int((time.perf_counter() - started_at) * 1000),
    )
    return org_id


async def require_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> tuple[dict, str]:
    """Require org + admin role. Returns (user, org_id). Raises 403 if not admin."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = _get_cached_service_client(settings)
    if is_platform_admin(client, current_user["user_id"]):
        return current_user, org_id
    r = (
        client.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", current_user["user_id"])
        .limit(1)
        .execute()
    )
    if not r.data or len(r.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    role = (r.data[0].get("role") or "").strip().lower()
    if not is_org_admin_role(role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user, org_id


async def require_org_member(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> tuple[dict, str, str]:
    """Require org membership. Returns (user, org_id, role). Raises 403 if not a member."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = _get_cached_service_client(settings)
    if is_platform_admin(client, current_user["user_id"]):
        return current_user, org_id, "admin"
    r = (
        client.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", current_user["user_id"])
        .limit(1)
        .execute()
    )
    if not r.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    role = (r.data[0].get("role") or "member").strip().lower()
    if not is_org_member_role(role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    return current_user, org_id, role


async def require_platform_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Require platform (Gravitre) admin. Returns user dict."""
    client = _get_cached_service_client(settings)
    if not is_platform_admin(client, current_user["user_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin required",
        )
    return current_user



async def get_environment_context(
    x_environment: Annotated[str | None, Header()] = None,
) -> str:
    """Optional environment selector; defaults to 'production'."""
    return normalize_environment_name(x_environment)


async def get_department_context(
    x_department: Annotated[str | None, Header()] = None,
) -> str | None:
    """Optional department scope for cowork desk / Lite filtering."""
    raw = (x_department or "").strip()
    if not raw or raw.lower() in {"all", "any", "*"}:
        return None
    return raw[:120]


def set_request_auth_context(user_id: str | None, org_id: str | None) -> None:
    """Set auth context for logging (middleware)."""
    if user_id:
        user_id_ctx.set(user_id)
    if org_id:
        org_id_ctx.set(org_id)
