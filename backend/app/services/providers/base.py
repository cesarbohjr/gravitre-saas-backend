"""Provider adapter interface + shared types for multi-provider failover.

Adapters translate the canonical internal message format to/from each provider's
native format, normalize usage, and map provider-specific exceptions to the typed
internal errors below. They must never leak provider SDK types to callers.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, TypedDict

logger = logging.getLogger(__name__)

STATE_CLOSED = "closed"
STATE_OPEN = "open"
STATE_HALF_OPEN = "half_open"


class Message(TypedDict):
    """Canonical internal message: role + content."""

    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class CompletionOptions:
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_s: float = 30.0


@dataclass
class ProviderResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model_used: str
    provider_used: str
    latency_ms: float
    # Subset of prompt_tokens served from the provider's prompt cache (when the
    # API reports it, e.g. OpenAI usage.prompt_tokens_details.cached_tokens).
    cached_tokens: int = 0
    raw_response: Any = field(default=None, repr=False)


@dataclass
class StreamChunk:
    """One chunk from a provider-native stream. Final chunk sets `done` + `response`."""

    delta: str = ""
    done: bool = False
    response: ProviderResponse | None = None


# ---------------------------------------------------------------------------
# Typed internal errors (provider SDK exceptions are mapped to these)
# ---------------------------------------------------------------------------


class ProviderError(RuntimeError):
    """Base class for provider adapter errors."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class ProviderUnavailableError(ProviderError):
    """Provider not configured, unreachable, timed out, or returned a server error.
    Failover SHOULD try the next provider."""


class ProviderRateLimitedError(ProviderError):
    """Provider returned a rate-limit / quota error. Failover SHOULD try next."""


class ProviderInvalidResponseError(ProviderError):
    """Bad request / prompt / input problem (e.g. 400, content policy, malformed
    output). This is NOT a provider availability problem — failover must NOT be
    attempted; the error is raised immediately."""


class AllProvidersFailedError(RuntimeError):
    """Raised when every provider in the failover chain failed."""

    def __init__(self, failures: list[tuple[str, str]]) -> None:
        self.failures = failures
        summary = "; ".join(f"{name}: {reason}" for name, reason in failures) or "no providers attempted"
        super().__init__(f"All AI providers failed ({summary})")


# ---------------------------------------------------------------------------
# Circuit breaker (per provider; optional Redis-backed shared state)
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """Trips after `failure_threshold` failures; stays open for `recovery_timeout`.

    A tripped (open) breaker counts as unavailable in the failover chain and is
    skipped immediately with no call attempt. After recovery_timeout elapses the
    breaker enters half_open and allows a single probe call.

    When `redis_client` is provided (or resolved via `redis_getter`), failure
    counts and state are shared across all worker instances. Any Redis error falls
    back to per-process in-memory state for that operation only.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        *,
        cooldown_s: float | None = None,
        provider_name: str | None = None,
        redis_client: Any | None = None,
        redis_getter: Callable[[], Any | None] | None = None,
        backend: str = "auto",
    ) -> None:
        if cooldown_s is not None:
            recovery_timeout = cooldown_s
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.cooldown_s = recovery_timeout  # backward-compatible alias
        self._default_provider = provider_name
        self._redis_client = redis_client
        self._redis_getter = redis_getter
        self._backend = (backend or "auto").strip().lower()
        self._failures: dict[str, int] = {}
        self._state: dict[str, str] = {}
        self._opened_at: dict[str, float] = {}
        self._lock = threading.RLock()

    def _keys(self, provider: str) -> dict[str, str]:
        """Redis key names for a provider's circuit state."""
        return {
            "failures": f"cb:{provider}:failures",
            "last_failure": f"cb:{provider}:last_failure",
            "state": f"cb:{provider}:state",
        }

    def _ttl(self) -> int:
        return max(1, int(self.recovery_timeout))

    def _resolve_provider(self, provider: str) -> str:
        return provider or self._default_provider or "default"

    def _get_redis(self) -> Any | None:
        """Return a Redis client when backend mode allows it, else None."""
        if self._backend == "memory":
            return None
        if self._backend == "redis":
            client = self._redis_client
            if client is None and self._redis_getter is not None:
                try:
                    client = self._redis_getter()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("circuit breaker redis getter failed: %s", str(exc))
                    return None
            return client
        # auto: use Redis when available
        client = self._redis_client
        if client is not None:
            return client
        if self._redis_getter is None:
            return None
        try:
            return self._redis_getter()
        except Exception as exc:  # noqa: BLE001
            logger.warning("circuit breaker redis getter failed: %s", str(exc))
            return None

    def _mem_get_state(self, provider: str) -> str:
        with self._lock:
            state = self._state.get(provider, STATE_CLOSED)
            if state == STATE_OPEN:
                opened = self._opened_at.get(provider)
                if opened is not None and (time.monotonic() - opened) >= self.recovery_timeout:
                    self._state[provider] = STATE_HALF_OPEN
                    return STATE_HALF_OPEN
            return state

    def _mem_is_open(self, provider: str) -> bool:
        state = self._mem_get_state(provider)
        return state == STATE_OPEN

    def is_open(self, provider: str) -> bool:
        """Return True when the circuit is open and requests should be skipped."""
        name = self._resolve_provider(provider)
        client = self._get_redis()
        if client is not None:
            try:
                keys = self._keys(name)
                state = client.get(keys["state"]) or STATE_CLOSED
                if state == STATE_OPEN:
                    last_raw = client.get(keys["last_failure"])
                    if last_raw is not None:
                        elapsed = time.time() - float(last_raw)
                        if elapsed >= self.recovery_timeout:
                            pipe = client.pipeline()
                            pipe.set(keys["state"], STATE_HALF_OPEN, ex=self._ttl())
                            pipe.execute()
                            return False
                    return True
                return False
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "circuit breaker redis is_open failed provider=%s error=%s",
                    name,
                    str(exc),
                )
        return self._mem_is_open(name)

    def record_success(self, provider: str) -> None:
        """Record a successful call; closes the circuit."""
        name = self._resolve_provider(provider)
        client = self._get_redis()
        if client is not None:
            try:
                keys = self._keys(name)
                pipe = client.pipeline()
                pipe.delete(keys["failures"], keys["last_failure"])
                pipe.set(keys["state"], STATE_CLOSED, ex=self._ttl())
                pipe.execute()
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "circuit breaker redis record_success failed provider=%s error=%s",
                    name,
                    str(exc),
                )
        with self._lock:
            self._failures[name] = 0
            self._state[name] = STATE_CLOSED
            self._opened_at.pop(name, None)

    def record_failure(self, provider: str) -> None:
        """Record a failed call; may trip the circuit open."""
        name = self._resolve_provider(provider)
        client = self._get_redis()
        if client is not None:
            try:
                keys = self._keys(name)
                state = client.get(keys["state"]) or STATE_CLOSED
                now = time.time()
                pipe = client.pipeline()
                if state == STATE_HALF_OPEN:
                    pipe.set(keys["state"], STATE_OPEN, ex=self._ttl())
                    pipe.set(keys["last_failure"], str(now), ex=self._ttl())
                else:
                    fail_key = keys["failures"]
                    pipe.incr(fail_key)
                    pipe.expire(fail_key, self._ttl())
                    pipe.set(keys["last_failure"], str(now), ex=self._ttl())
                    pipe.execute()
                    count = int(client.get(fail_key) or 0)
                    if count >= self.failure_threshold:
                        client.set(keys["state"], STATE_OPEN, ex=self._ttl())
                    return
                pipe.execute()
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "circuit breaker redis record_failure failed provider=%s error=%s",
                    name,
                    str(exc),
                )
        with self._lock:
            state = self._mem_get_state(name)
            if state == STATE_HALF_OPEN:
                self._state[name] = STATE_OPEN
                self._opened_at[name] = time.monotonic()
                return
            count = self._failures.get(name, 0) + 1
            self._failures[name] = count
            if count >= self.failure_threshold:
                self._state[name] = STATE_OPEN
                self._opened_at[name] = time.monotonic()


# ---------------------------------------------------------------------------
# Adapter interface
# ---------------------------------------------------------------------------


class ProviderAdapter(ABC):
    provider_name: str = "base"
    supported_models: list[str] = []

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        model: str,
        options: CompletionOptions,
    ) -> ProviderResponse:
        """Run a chat completion and return a normalized ProviderResponse."""

    @abstractmethod
    def embed(self, text: str, model: str) -> list[float]:
        """Return an embedding vector for `text`."""

    async def stream(
        self,
        messages: list[Message],
        model: str,
        options: CompletionOptions,
    ) -> AsyncIterator[StreamChunk]:
        """Stream chat tokens. Default falls back to a single complete() call."""
        resp = await self.complete(messages, model, options)
        if resp.content:
            yield StreamChunk(delta=resp.content)
        yield StreamChunk(done=True, response=resp)

    @abstractmethod
    def is_available(self) -> bool:
        """True when the provider is configured and its SDK is importable."""


async def retry_provider_call(
    attempt: Callable[[], Awaitable["ProviderResponse"]],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.4,
) -> "ProviderResponse":
    """Run an adapter attempt with exponential backoff.

    Retries on transient errors (ProviderUnavailableError / ProviderRateLimitedError)
    but NOT on ProviderInvalidResponseError (input/prompt problem — raised at once).
    """
    delay = base_delay
    last_exc: Exception | None = None
    for i in range(max_attempts):
        try:
            return await attempt()
        except ProviderInvalidResponseError:
            raise
        except (ProviderUnavailableError, ProviderRateLimitedError) as exc:
            last_exc = exc
            if i == max_attempts - 1:
                break
            await asyncio.sleep(delay)
            delay *= 2
    assert last_exc is not None
    raise last_exc


def extract_system(messages: list[Message]) -> tuple[str | None, list[Message]]:
    """Split a leading/embedded system message from the conversation.

    Returns (system_text_or_None, non_system_messages). System messages are
    concatenated; useful for providers (Anthropic) that take system separately.
    """
    system_parts: list[str] = []
    rest: list[Message] = []
    for m in messages:
        if m["role"] == "system":
            if m["content"]:
                system_parts.append(m["content"])
        else:
            rest.append(m)
    system_text = "\n\n".join(system_parts) if system_parts else None
    return system_text, rest
