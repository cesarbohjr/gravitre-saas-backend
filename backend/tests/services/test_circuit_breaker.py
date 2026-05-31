"""Tests for the Redis-backed CircuitBreaker (with in-process fallback)."""
from __future__ import annotations

import logging

from app.services.providers.base import CircuitBreaker, STATE_OPEN


class _FakePipeline:
    def __init__(self, redis: "_FakeRedis"):
        self._redis = redis
        self._ops: list[tuple] = []

    def incr(self, key):
        self._ops.append(("incr", key))
        return self

    def expire(self, key, ttl):
        self._ops.append(("expire", key, ttl))
        return self

    def set(self, key, val, ex=None):
        self._ops.append(("set", key, val, ex))
        return self

    def delete(self, *keys):
        self._ops.append(("delete", keys))
        return self

    def execute(self):
        for op in self._ops:
            if op[0] == "incr":
                self._redis.incr(op[1])
            elif op[0] == "expire":
                self._redis.expire(op[1], op[2])
            elif op[0] == "set":
                self._redis.set(op[1], op[2], ex=op[3])
            elif op[0] == "delete":
                self._redis.delete(*op[1])
        self._ops.clear()
        return True


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

    def get(self, key):
        return self.kv.get(key)

    def exists(self, key):
        return 1 if key in self.kv else 0

    def delete(self, *keys):
        for k in keys:
            self.kv.pop(k, None)
        return len(keys)

    def pipeline(self):
        return _FakePipeline(self)


def test_redis_breaker_opens_and_recovers():
    redis = _FakeRedis()
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60, redis_client=redis)
    assert cb.is_open("openai") is False
    cb.record_failure("openai")
    assert cb.is_open("openai") is False  # 1 failure
    cb.record_failure("openai")
    assert cb.is_open("openai") is True   # 2 -> tripped, shared via redis
    cb.record_success("openai")
    assert cb.is_open("openai") is False  # cleared


def test_redis_breaker_isolated_per_provider():
    redis = _FakeRedis()
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60, redis_client=redis)
    cb.record_failure("anthropic")
    assert cb.is_open("anthropic") is True
    assert cb.is_open("openai") is False


def test_shared_state_across_two_breaker_instances():
    """Simulates two Railway workers sharing Redis circuit state."""
    redis = _FakeRedis()
    worker_a = CircuitBreaker(failure_threshold=2, recovery_timeout=60, redis_client=redis)
    worker_b = CircuitBreaker(failure_threshold=2, recovery_timeout=60, redis_client=redis)
    worker_a.record_failure("openai")
    worker_a.record_failure("openai")
    assert worker_b.is_open("openai") is True


def test_redis_failure_falls_back_to_memory():
    class _BrokenRedis:
        def get(self, key):
            raise ConnectionError("redis down")

        def pipeline(self):
            raise ConnectionError("redis down")

        def incr(self, key):
            raise ConnectionError("redis down")

        def set(self, key, val, ex=None):
            raise ConnectionError("redis down")

        def expire(self, key, ttl):
            raise ConnectionError("redis down")

        def delete(self, *keys):
            raise ConnectionError("redis down")

    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60, redis_client=_BrokenRedis())
    cb.record_failure("openai")
    assert cb.is_open("openai") is True


def test_falls_back_to_local_when_redis_getter_errors():
    def bad():
        raise RuntimeError("redis down")

    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60, redis_getter=bad)
    cb.record_failure("openai")  # redis errors -> local path
    assert cb.is_open("openai") is True


def test_no_redis_uses_local():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60, backend="memory")
    cb.record_failure("gemini")
    assert cb.is_open("gemini") is False
    cb.record_failure("gemini")
    assert cb.is_open("gemini") is True


def test_backend_memory_forces_local_even_with_redis():
    redis = _FakeRedis()
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60, redis_client=redis, backend="memory")
    cb.record_failure("openai")
    assert cb.is_open("openai") is True
    assert "cb:openai:state" not in redis.kv


def test_half_open_failure_reopens(monkeypatch):
    redis = _FakeRedis()
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, redis_client=redis)
    cb.record_failure("openai")
    assert cb.is_open("openai") is True
    monkeypatch.setattr(
        "app.services.providers.base.time.time",
        lambda: redis.kv.get("cb:openai:last_failure", 0) + 1.0,
    )
    assert cb.is_open("openai") is False  # half_open allows probe
    cb.record_failure("openai")
    assert redis.kv.get("cb:openai:state") == STATE_OPEN


def test_state_keys_written_to_redis():
    redis = _FakeRedis()
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60, redis_client=redis)
    cb.record_failure("gemini")
    assert redis.kv.get("cb:gemini:failures") == 1
    assert "cb:gemini:last_failure" in redis.kv
