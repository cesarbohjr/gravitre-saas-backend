"""Short-TTL, singleflight cache for `get_org_context` resolution results.

Perf/regression fix (2026-09-07). Root cause, confirmed live: `get_org_context`
(backend/app/auth/dependencies.py) resolves on nearly every authenticated
request via two sequential, synchronous (blocking) Supabase network
round-trips (`is_platform_admin`, `list_member_org_ids`), run directly inside
an `async def` FastAPI dependency with no `await`/`asyncio.to_thread` —
meaning each call blocks the *entire* event loop for the full round-trip
duration.

Confirmed live (2026-09-07, `.tmp_probe_turn_taking_concurrent.py` against the
deployed backend): a burst of 15 concurrent calls to
`POST /api/voice/turn-taking/event` — the real shape of Deepgram's rapid
interim-transcript stream, which the frontend fires unawaited/unserialized
(see `apps/web/hooks/use-voice-duplex-session.ts`'s WS `onmessage` handler) —
took a uniform ~2,545-2,602ms *each* (p50 2,548ms, p95 2,602ms). This is the
classic event-loop-serialization signature: the whole burst's blocking I/O
gets processed one request at a time on the single blocked event loop,
exactly matching the live user-reported 1-6s `/turn-taking/event` symptom.
Fully sequential (non-concurrent) calls from one client, by contrast,
measured ~220-300ms each (`.tmp_probe_turn_taking_latency.py`) — confirming
the bottleneck is concurrency-driven event-loop blocking, not a uniformly
slow single call.

This module adds two, independent, additive mechanisms — neither changes the
underlying authorization semantics of `get_org_context`, only how often (and
how blockingly) the real check runs:

  1. A short-TTL (`_TTL_SECONDS`) result cache keyed by
     `(user_id, requested_org_id)`, so the overwhelming majority of
     same-user, same-session calls (e.g. every turn-taking event within one
     active voice utterance, which all carry the same `x-org-id` header)
     never touch Supabase at all.
  2. Singleflight de-duplication for concurrent cache-misses on the same
     key, so a burst of N concurrent first-calls (e.g. the very first
     turn-taking event of a session, hit by several near-simultaneous
     Deepgram interim events before the cache is warm) triggers exactly ONE
     live resolution, not N redundant ones.

TTL is deliberately short — 20s, not the 45-60s used for the connector-
snapshot / voice-status caches elsewhere in this codebase — because this
cache backs a security-relevant authorization decision (org membership).
20s bounds the staleness window for a revoked membership to something
operationally negligible while still absorbing the real call pattern (many
calls per second within one active utterance, all sharing one cache key).
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")

_TTL_SECONDS = 20
# key -> (expires_at_epoch_seconds, resolved_org_id_or_none, forbidden)
_CACHE: dict[str, tuple[float, str | None, bool]] = {}
# key -> in-flight resolution task, for singleflight de-dup of concurrent misses
_INFLIGHT: dict[str, "asyncio.Task[str | None]"] = {}


def _cache_key(user_id: str, requested_org_id: str) -> str:
    return f"{user_id}:{requested_org_id or ''}"


def get_cached_org_context(user_id: str, requested_org_id: str) -> tuple[str | None, bool] | None:
    """Return `(org_id, forbidden)` for a fresh cache hit, else `None` (miss/expired)."""
    key = _cache_key(user_id, requested_org_id)
    row = _CACHE.get(key)
    if not row:
        return None
    expires_at, org_id, forbidden = row
    if time.time() > expires_at:
        _CACHE.pop(key, None)
        return None
    return org_id, forbidden


def set_cached_org_context(
    user_id: str,
    requested_org_id: str,
    *,
    org_id: str | None,
    forbidden: bool,
    ttl_seconds: int = _TTL_SECONDS,
) -> None:
    key = _cache_key(user_id, requested_org_id)
    _CACHE[key] = (time.time() + max(1, ttl_seconds), org_id, forbidden)


def clear_org_context_cache() -> None:
    """Test-only / ops escape hatch — never called from request-serving code."""
    _CACHE.clear()
    _INFLIGHT.clear()


async def resolve_singleflight(key: str, factory: Callable[[], Awaitable[T]]) -> T:
    """Run `factory()` at most once per `key` for overlapping concurrent callers.

    Callers that arrive while a resolution for `key` is already in flight
    `await` the SAME task instead of issuing their own duplicate (blocking)
    Supabase calls. This is the fix for the thundering-herd shape of the live
    regression: N concurrent turn-taking calls sharing one fresh/expired
    cache key must resolve org membership exactly once, not N times.
    """
    existing = _INFLIGHT.get(key)
    if existing is not None and not existing.done():
        return await existing
    task: "asyncio.Task[T]" = asyncio.ensure_future(factory())
    _INFLIGHT[key] = task  # type: ignore[assignment]
    try:
        return await task
    finally:
        if _INFLIGHT.get(key) is task:  # type: ignore[comparison-overlap]
            del _INFLIGHT[key]
