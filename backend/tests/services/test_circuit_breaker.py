"""Tests for the Redis-backed CircuitBreaker (with in-process fallback)."""
from __future__ import annotations

from app.services.providers.base import CircuitBreaker


class _FakeRedis:
    def __init__(self):
        self.kv: dict = {}

    def incr(self, key):
        self.kv[key] = int(self.kv.get(key, 0)) + 1
        return self.kv[key]

    def expire(self, key, ttl):
        return True

    def set(self, key, val, ex=None):
        self.kv[key] = val
        return True

    def exists(self, key):
        return 1 if key in self.kv else 0

    def delete(self, *keys):
        for k in keys:
            self.kv.pop(k, None)
        return len(keys)


def test_redis_breaker_opens_and_recovers():
    redis = _FakeRedis()
    cb = CircuitBreaker(failure_threshold=2, cooldown_s=60, redis_getter=lambda: redis)
    assert cb.is_open("openai") is False
    cb.record_failure("openai")
    assert cb.is_open("openai") is False  # 1 failure
    cb.record_failure("openai")
    assert cb.is_open("openai") is True   # 2 -> tripped, shared via redis
    cb.record_success("openai")
    assert cb.is_open("openai") is False  # cleared


def test_redis_breaker_isolated_per_provider():
    redis = _FakeRedis()
    cb = CircuitBreaker(failure_threshold=1, cooldown_s=60, redis_getter=lambda: redis)
    cb.record_failure("anthropic")
    assert cb.is_open("anthropic") is True
    assert cb.is_open("openai") is False


def test_falls_back_to_local_when_redis_getter_errors():
    def bad():
        raise RuntimeError("redis down")

    cb = CircuitBreaker(failure_threshold=1, cooldown_s=60, redis_getter=bad)
    cb.record_failure("openai")  # redis errors -> local path
    assert cb.is_open("openai") is True


def test_no_redis_getter_uses_local():
    cb = CircuitBreaker(failure_threshold=2, cooldown_s=60)
    cb.record_failure("gemini")
    assert cb.is_open("gemini") is False
    cb.record_failure("gemini")
    assert cb.is_open("gemini") is True
