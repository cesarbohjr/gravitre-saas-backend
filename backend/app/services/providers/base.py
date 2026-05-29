"""Provider adapter interface + shared types for multi-provider failover.

Adapters translate the canonical internal message format to/from each provider's
native format, normalize usage, and map provider-specific exceptions to the typed
internal errors below. They must never leak provider SDK types to callers.
"""
from __future__ import annotations

import asyncio
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, TypedDict


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
# Circuit breaker (per provider, in-process)
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """Trips after `failure_threshold` failures; stays open for `cooldown_s`.

    A tripped (open) breaker counts as unavailable in the failover chain and is
    skipped immediately with no call attempt.

    When `redis_getter` returns a Redis client, failure counts + open state are
    shared across all instances (keys auto-expire after cooldown). Any Redis
    error falls back to the per-process state, so behavior degrades gracefully.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_s: float = 60.0,
        redis_getter: Any = None,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_s = cooldown_s
        self._failures: dict[str, int] = {}
        self._opened_at: dict[str, float] = {}
        self._lock = threading.Lock()
        self._redis_getter = redis_getter

    def _redis(self):
        if self._redis_getter is None:
            return None
        try:
            return self._redis_getter()
        except Exception:  # noqa: BLE001
            return None

    def is_open(self, provider: str) -> bool:
        client = self._redis()
        if client is not None:
            try:
                return bool(client.exists(f"cb:open:{provider}"))
            except Exception:  # noqa: BLE001
                pass
        with self._lock:
            opened = self._opened_at.get(provider)
            if opened is None:
                return False
            if (time.monotonic() - opened) >= self.cooldown_s:
                # Cooldown elapsed -> half-open: clear so the next call can probe.
                self._opened_at.pop(provider, None)
                self._failures[provider] = 0
                return False
            return True

    def record_success(self, provider: str) -> None:
        client = self._redis()
        if client is not None:
            try:
                client.delete(f"cb:fail:{provider}", f"cb:open:{provider}")
                return
            except Exception:  # noqa: BLE001
                pass
        with self._lock:
            self._failures[provider] = 0
            self._opened_at.pop(provider, None)

    def record_failure(self, provider: str) -> None:
        client = self._redis()
        if client is not None:
            try:
                fail_key = f"cb:fail:{provider}"
                count = int(client.incr(fail_key))
                client.expire(fail_key, int(self.cooldown_s))
                if count >= self.failure_threshold:
                    client.set(f"cb:open:{provider}", "1", ex=int(self.cooldown_s))
                return
            except Exception:  # noqa: BLE001
                pass
        with self._lock:
            count = self._failures.get(provider, 0) + 1
            self._failures[provider] = count
            if count >= self.failure_threshold and provider not in self._opened_at:
                self._opened_at[provider] = time.monotonic()


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
