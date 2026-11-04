"""Voice inference failure boundary: typed, sanitized, and side-effect free.

A failed model request is not an ambiguous user request. When every configured
provider is unavailable, voice must not re-enter a generic clarification path.
Do not put vendor exception bodies, account status, keys or prompts in speech.
"""
from __future__ import annotations

from typing import Any

_PROVIDER_FAILURE_CLASSES = frozenset({
    "AllProvidersFailedError",
    "ProviderUnavailableError",
    "ProviderAuthenticationUnavailable",
    "AuthenticationError",
    "PermissionDeniedError",
    "RateLimitError",
    "APIConnectionError",
    "APITimeoutError",
    "TimeoutError",
    "ConnectTimeout",
    "ReadTimeout",
})
# APIStatusError can cover invalid input (400), not solely provider downtime.
# Classify it only when the telemetry supplies an explicitly recognized category.
_PROVIDER_FAILURE_CATEGORIES = frozenset({
    "authentication", "auth", "auth_rejected", "auth_cooldown",
    "insufficient_credits", "insufficient_quota", "billing",
    "rate_limit", "provider_unavailable", "timeout",
})


def unavailable_voice_model_reply(result: Any) -> str | None:
    """Return an honest voice reply only for a *typed* provider failure.

    Never use the exception body's prose as the user-facing answer, and do not
    infer account credit state from a generic exception or keyword in a prompt.
    Other errors deliberately retain the existing fallthrough behavior.
    """
    if getattr(result, "outcome_kind", None) != "error":
        return None
    breakdown = getattr(result, "latency_breakdown", None)
    breakdown = breakdown if isinstance(breakdown, dict) else {}
    failure_class = str(breakdown.get("error") or getattr(result, "error", "") or "")
    category = str(breakdown.get("provider_error_category") or "").strip().lower()
    if failure_class not in _PROVIDER_FAILURE_CLASSES and category not in _PROVIDER_FAILURE_CATEGORIES:
        return None
    return (
        "I couldn't complete that request because the AI model service "
        "is unavailable right now. I haven't completed the task. "
        "Please try again after model access is restored."
    )
