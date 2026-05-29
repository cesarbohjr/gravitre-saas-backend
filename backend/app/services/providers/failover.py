"""Provider priority resolution + failover chain execution."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.config import MODEL_TIERS
from app.core.logging import get_logger
from app.services.providers.base import (
    AllProvidersFailedError,
    CircuitBreaker,
    CompletionOptions,
    Message,
    ProviderAdapter,
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderResponse,
    ProviderUnavailableError,
)

logger = get_logger(__name__)

_PROVIDER_ORDER = ["openai", "anthropic", "gemini"]


def _provider_order(preferred: str, complexity: str) -> list[str]:
    pref = (preferred or "openai").strip().lower()
    if pref == "auto":
        # Bias the strongest reasoning provider first on high complexity, and the
        # cheapest/fastest first on low complexity.
        if complexity == "low":
            return ["openai", "anthropic", "gemini"]
        if complexity == "high":
            return ["anthropic", "openai", "gemini"]
        return ["openai", "anthropic", "gemini"]
    if pref in _PROVIDER_ORDER:
        return [pref, *[p for p in _PROVIDER_ORDER if p != pref]]
    return list(_PROVIDER_ORDER)


def build_priority(preferred: str, complexity: str) -> list[tuple[str, str]]:
    """Return an ordered [(provider_name, model_id)] list for the given preference
    and complexity tier."""
    tier = MODEL_TIERS.get(complexity, MODEL_TIERS["medium"])
    order = _provider_order(preferred, complexity)
    priority: list[tuple[str, str]] = []
    for name in order:
        model = tier.get(name)
        if model:
            priority.append((name, model))
    return priority


@dataclass
class FailoverResult:
    response: ProviderResponse
    attempts: list[tuple[str, str]] = field(default_factory=list)  # (provider, outcome)


async def run_failover(
    adapters: dict[str, ProviderAdapter],
    priority: list[tuple[str, str]],
    messages: list[Message],
    options: CompletionOptions,
    breaker: CircuitBreaker,
) -> FailoverResult:
    """Try each (provider, model) in order. Returns on first success.

    - ProviderUnavailableError / ProviderRateLimitedError -> log + try next.
    - ProviderInvalidResponseError -> raise immediately (no failover).
    - Tripped circuit breaker -> skip provider (counts as unavailable).
    - All fail -> AllProvidersFailedError(summary).
    """
    attempts: list[tuple[str, str]] = []
    failures: list[tuple[str, str]] = []

    for provider_name, model in priority:
        adapter = adapters.get(provider_name)
        if adapter is None or not adapter.is_available():
            attempts.append((provider_name, "skipped:unavailable"))
            failures.append((provider_name, "unavailable/not-configured"))
            continue
        if breaker.is_open(provider_name):
            attempts.append((provider_name, "skipped:circuit_open"))
            failures.append((provider_name, "circuit breaker open"))
            continue
        try:
            response = await adapter.complete(messages, model, options)
            breaker.record_success(provider_name)
            attempts.append((provider_name, "success"))
            return FailoverResult(response=response, attempts=attempts)
        except ProviderInvalidResponseError:
            # Input/prompt problem — do not fail over.
            attempts.append((provider_name, "invalid_response"))
            raise
        except (ProviderUnavailableError, ProviderRateLimitedError) as exc:
            breaker.record_failure(provider_name)
            reason = type(exc).__name__
            attempts.append((provider_name, f"failed:{reason}"))
            failures.append((provider_name, str(exc)))
            logger.warning("provider failover: %s failed (%s), trying next", provider_name, reason)
            continue

    raise AllProvidersFailedError(failures)
