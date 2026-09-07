"""Mutation-proof tests for the 2026-09-07 get_org_context latency fix.

Root cause and live evidence: see backend/app/auth/org_context_cache.py's
module docstring. Short version — `get_org_context` did two sequential,
blocking Supabase network calls inline on the event loop, on every single
call; a live burst of 15 concurrent `/turn-taking/event` calls (the real
Deepgram interim-transcript pattern) serialized into a uniform ~2.5s each.

These tests prove, without any live network dependency, that:
  1. A cache hit never touches the (mocked) live-resolution path at all.
  2. A cached "forbidden" result re-raises 403 without a second live lookup.
  3. TTL expiry correctly falls back to a fresh live lookup.
  4. Concurrent callers sharing the same (user_id, requested_org_id) key
     collapse into exactly ONE live resolution (singleflight), not N.
  5. The two independent membership lookups inside a live resolution run
     genuinely concurrently (via asyncio.to_thread), not sequentially — the
     actual mechanism that halves cold-path latency and stops one slow
     lookup from blocking the other.
  6. The Supabase service-role client is a true singleton across calls with
     the same settings, and distinct across differing settings.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request

from app.auth.dependencies import _get_cached_service_client, get_org_context
from app.auth.org_context_cache import (
    clear_org_context_cache,
    get_cached_org_context,
    set_cached_org_context,
)
from app.config import Settings


def _settings(url: str = "https://test.supabase.co", key: str = "service") -> Settings:
    return Settings(
        app_env="dev",
        supabase_url=url,
        supabase_anon_key="anon",
        supabase_service_role_key=key,
        supabase_jwt_secret="secret",
    )


def _request(*, org_id: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if org_id:
        headers.append((b"x-org-id", org_id.encode()))
    return Request(
        {
            "type": "http",
            "headers": headers,
            "query_string": b"",
            "path": "/api/voice/turn-taking/event",
            "method": "POST",
        }
    )


@pytest.fixture(autouse=True)
def _mock_supabase_create_client():
    """Every live-path test below hits `_get_cached_service_client`, which — on
    a genuine cache miss — calls the real `supabase.create_client(...)`.
    Confirmed by direct measurement: constructing a real Client (even against
    a fake, unreachable `https://test.supabase.co` URL, as `test_org_context.py`
    also uses) costs ~0.9-1.1s of real wall-clock time in this environment —
    entirely orthogonal to anything this file's timing-sensitive assertions
    care about (singleflight dedup, intra-request concurrency). Without this,
    every timing assertion below would really be measuring Client-construction
    cost, not the mechanism under test — exactly the kind of "one layer too
    low" measurement error this program has been burned by before. Matches
    `test_org_context.py`'s own `patch("supabase.create_client", ...)`
    convention.
    """
    with patch("supabase.create_client", return_value=MagicMock()):
        yield


# ─── 1-3: TTL cache correctness ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_hit_skips_live_lookup_entirely():
    set_cached_org_context("user-1", "org-b", org_id="org-b", forbidden=False)
    with patch("app.auth.dependencies.is_platform_admin") as admin_mock:
        with patch("app.services.org_membership.list_member_org_ids") as members_mock:
            org_id = await get_org_context(
                _request(org_id="org-b"),
                {"user_id": "user-1", "email": "u@example.com"},
                _settings(),
            )
    assert org_id == "org-b"
    admin_mock.assert_not_called()
    members_mock.assert_not_called()


@pytest.mark.asyncio
async def test_cached_forbidden_reraises_403_without_second_live_lookup():
    set_cached_org_context("user-2", "org-other", org_id=None, forbidden=True)
    with patch("app.auth.dependencies.is_platform_admin") as admin_mock:
        with patch("app.services.org_membership.list_member_org_ids") as members_mock:
            with pytest.raises(HTTPException) as exc_info:
                await get_org_context(
                    _request(org_id="org-other"),
                    {"user_id": "user-2", "email": "u@example.com"},
                    _settings(),
                )
    assert exc_info.value.status_code == 403
    admin_mock.assert_not_called()
    members_mock.assert_not_called()


@pytest.mark.asyncio
async def test_expired_cache_entry_falls_back_to_live_lookup():
    # Write a real-looking cache row but with an already-past expiry.
    from app.auth import org_context_cache as cache_module

    key = cache_module._cache_key("user-3", "org-a")
    cache_module._CACHE[key] = (time.time() - 5, "org-stale", False)

    with patch("app.auth.dependencies.is_platform_admin", return_value=False):
        with patch(
            "app.services.org_membership.list_member_org_ids",
            return_value=["org-a"],
        ):
            org_id = await get_org_context(
                _request(org_id="org-a"),
                {"user_id": "user-3", "email": "u@example.com"},
                _settings(),
            )
    # Fresh live lookup, not the stale cached value.
    assert org_id == "org-a"
    assert get_cached_org_context("user-3", "org-a") == ("org-a", False)


# ─── 4: singleflight de-duplication ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_concurrent_calls_same_key_trigger_exactly_one_live_lookup():
    """The exact shape of the live regression: N concurrent turn-taking calls
    from one fresh cache key must resolve org membership once, not N times.
    """
    call_count = {"n": 0}

    def _slow_list_member_org_ids(_client, _user_id):
        call_count["n"] += 1
        time.sleep(0.05)
        return ["org-a"]

    with patch("app.auth.dependencies.is_platform_admin", return_value=False):
        with patch(
            "app.services.org_membership.list_member_org_ids",
            side_effect=_slow_list_member_org_ids,
        ):
            results = await asyncio.gather(
                *[
                    get_org_context(
                        _request(org_id="org-a"),
                        {"user_id": "user-4", "email": "u@example.com"},
                        _settings(),
                    )
                    for _ in range(8)
                ]
            )

    assert results == ["org-a"] * 8
    assert call_count["n"] == 1, (
        f"expected exactly 1 real membership lookup for 8 concurrent callers "
        f"sharing one cache key, got {call_count['n']} — singleflight dedup regressed"
    )


@pytest.mark.asyncio
async def test_concurrent_forbidden_calls_same_key_all_raise_403():
    with patch("app.auth.dependencies.is_platform_admin", return_value=False):
        with patch(
            "app.services.org_membership.list_member_org_ids",
            return_value=["org-a"],
        ):
            outcomes = await asyncio.gather(
                *[
                    get_org_context(
                        _request(org_id="org-not-a-member"),
                        {"user_id": "user-5", "email": "u@example.com"},
                        _settings(),
                    )
                    for _ in range(5)
                ],
                return_exceptions=True,
            )
    assert len(outcomes) == 5
    for outcome in outcomes:
        assert isinstance(outcome, HTTPException)
        assert outcome.status_code == 403


# ─── 5: genuine concurrency inside a live resolution ────────────────────────


@pytest.mark.asyncio
async def test_platform_admin_and_member_lookup_run_concurrently_not_sequentially():
    """Both blocking lookups sleep 0.15s each. Sequential execution would take
    >=0.3s; genuine concurrency (asyncio.to_thread + gather) should complete
    in well under that. This is the mechanism, not just the outcome — proves
    the fix isn't a no-op that happens to still pass functionally.
    """

    def _slow_is_platform_admin(_client, _user_id):
        time.sleep(0.15)
        return False

    def _slow_list_member_org_ids(_client, _user_id):
        time.sleep(0.15)
        return ["org-a"]

    # Warm the (otherwise lazy, function-local) `app.services.org_membership`
    # import BEFORE starting the timer. This module — and its transitive
    # imports — cost ~1-3s to import cold in this test process (confirmed via
    # direct measurement); that cost is real but entirely orthogonal to what
    # this test verifies (genuine intra-request concurrency) and, in the real
    # running app, is already long paid by app-startup time before any
    # request is served. Without this warm-up the assertion below would be
    # measuring import latency, not concurrency.
    import app.services.org_membership  # noqa: F401

    with patch("app.auth.dependencies.is_platform_admin", side_effect=_slow_is_platform_admin):
        with patch(
            "app.services.org_membership.list_member_org_ids",
            side_effect=_slow_list_member_org_ids,
        ):
            started = time.perf_counter()
            org_id = await get_org_context(
                _request(org_id="org-a"),
                {"user_id": "user-6", "email": "u@example.com"},
                _settings(),
            )
            elapsed = time.perf_counter() - started

    assert org_id == "org-a"
    assert elapsed < 0.28, (
        f"expected concurrent (~0.15s) lookups, measured {elapsed:.3f}s — "
        "looks sequential (~0.3s), concurrency fix regressed"
    )


# ─── 6: singleton service client ────────────────────────────────────────────


def test_service_client_is_a_singleton_per_settings():
    with patch("supabase.create_client") as create_mock:
        create_mock.side_effect = lambda *a, **k: MagicMock()
        settings = _settings()
        client_1 = _get_cached_service_client(settings)
        client_2 = _get_cached_service_client(settings)
    assert client_1 is client_2
    create_mock.assert_called_once()


def test_service_client_differs_across_distinct_settings():
    with patch("supabase.create_client") as create_mock:
        create_mock.side_effect = lambda *a, **k: MagicMock()
        client_a = _get_cached_service_client(_settings(url="https://a.supabase.co"))
        client_b = _get_cached_service_client(_settings(url="https://b.supabase.co"))
    assert client_a is not client_b
    assert create_mock.call_count == 2


def test_clear_org_context_cache_is_idempotent_and_empties_state():
    set_cached_org_context("user-x", "org-x", org_id="org-x", forbidden=False)
    assert get_cached_org_context("user-x", "org-x") is not None
    clear_org_context_cache()
    assert get_cached_org_context("user-x", "org-x") is None
    clear_org_context_cache()  # idempotent, must not raise
