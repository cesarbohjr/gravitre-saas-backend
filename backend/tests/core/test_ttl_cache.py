"""Unit tests for app.core.ttl_cache.TTLCache."""
from __future__ import annotations

import threading

import pytest

from app.core.ttl_cache import TTLCache, ttl_from_env


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_set_get_and_expiry_uses_injected_monotonic_clock():
    clock = FakeClock()
    cache = TTLCache(30, clock=clock)
    cache.set("k", {"v": 1})
    assert cache.get("k") == {"v": 1}
    clock.now += 29.9
    assert cache.get("k") == {"v": 1}
    clock.now += 0.2
    assert cache.get("k") is None
    assert len(cache) == 0


def test_values_are_deep_copied_in_and_out():
    cache = TTLCache(30)
    original = {"plan": {"features": {"rbac": True}}, "list": [1]}
    cache.set("k", original)
    original["plan"]["features"]["rbac"] = False
    first = cache.get("k")
    assert first["plan"]["features"]["rbac"] is True
    first["list"].append(2)
    first["plan"]["features"]["rbac"] = "mutated"
    second = cache.get("k")
    assert second == {"plan": {"features": {"rbac": True}}, "list": [1]}


def test_bounded_size_evicts_oldest_write_first():
    cache = TTLCache(30, max_entries=3)
    for i in range(5):
        cache.set(i, i)
    assert len(cache) == 3
    assert cache.get(0) is None and cache.get(1) is None
    assert [cache.get(i) for i in (2, 3, 4)] == [2, 3, 4]
    # Re-writing a key moves it to the newest position.
    cache.set(2, "again")
    cache.set(5, 5)
    assert cache.get(3) is None
    assert cache.get(2) == "again"


def test_invalidate_tag_drops_only_tagged_entries():
    cache = TTLCache(30)
    cache.set("a", 1, tags=[("org", "o1")])
    cache.set("b", 2, tags=[("org", "o1"), ("user", "u1")])
    cache.set("c", 3, tags=[("org", "o2")])
    assert cache.invalidate_tag(("org", "o1")) == 2
    assert cache.get("a") is None and cache.get("b") is None
    assert cache.get("c") == 3
    cache.invalidate("c")
    assert cache.get("c") is None


def test_set_with_stale_token_is_skipped_after_invalidation():
    cache = TTLCache(30)
    token = cache.token()
    cache.invalidate_tag(("org", "anything"))  # a write happened mid-compute
    assert cache.set("k", "stale", token=token) is False
    assert cache.get("k") is None
    fresh = cache.token()
    assert cache.set("k", "fresh", token=fresh) is True
    assert cache.get("k") == "fresh"


def test_zero_ttl_disables_cache():
    cache = TTLCache(0)
    assert cache.enabled is False
    assert cache.set("k", 1) is False
    assert cache.get("k", "default") == "default"


def test_max_entries_must_be_positive():
    with pytest.raises(ValueError):
        TTLCache(30, max_entries=0)


def test_ttl_from_env(monkeypatch):
    monkeypatch.delenv("X_TTL_TEST", raising=False)
    assert ttl_from_env("X_TTL_TEST", 30.0) == 30.0
    monkeypatch.setenv("X_TTL_TEST", "5")
    assert ttl_from_env("X_TTL_TEST", 30.0) == 5.0
    monkeypatch.setenv("X_TTL_TEST", "0")
    assert ttl_from_env("X_TTL_TEST", 30.0) == 0.0
    monkeypatch.setenv("X_TTL_TEST", "nope")
    assert ttl_from_env("X_TTL_TEST", 30.0) == 30.0
    monkeypatch.setenv("X_TTL_TEST", "-3")
    assert ttl_from_env("X_TTL_TEST", 30.0) == 0.0


def test_concurrent_access_is_safe_and_stays_bounded():
    cache = TTLCache(30, max_entries=50)
    errors: list[BaseException] = []

    def worker(n: int) -> None:
        try:
            for i in range(500):
                key = (n, i % 80)
                cache.set(key, {"n": n, "i": i}, tags=[("org", str(i % 7))])
                cache.get(key)
                if i % 50 == 0:
                    cache.invalidate_tag(("org", str(n % 7)))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(cache) <= 50
