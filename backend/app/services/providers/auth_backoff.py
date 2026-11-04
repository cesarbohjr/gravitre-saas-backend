"""Bounded, process-local backoff for rejected provider credentials.

Only a structured HTTP 401 opens the circuit. No provider switch, SDK retry,
credential value, exception body or prompt is persisted by this module.
"""
from __future__ import annotations

import hashlib
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator


class ProviderAuthenticationUnavailable(RuntimeError):
    """Safe diagnostic for callers, logs and audit payloads."""

    def __init__(self, provider: str, *, suppressed: bool) -> None:
        self.provider = provider
        self.suppressed = suppressed
        self.category = "provider_authentication_backoff" if suppressed else "provider_authentication_failed"
        super().__init__(f"{self.category}:{provider}")


class ProviderAuthBackoff:
    def __init__(self, *, cooldown_s: float = 60.0, capacity: int = 128, clock=time.monotonic) -> None:
        self._cooldown_s = cooldown_s
        self._capacity = capacity
        self._clock = clock
        self._blocked: dict[tuple[str, bytes], float] = {}
        self._lock = threading.Lock()

    @contextmanager
    def guard(self, provider: str, credential: str, endpoint: str = "") -> Iterator[None]:
        # Empty/missing credentials are handled by the caller's existing checks.
        # Fingerprints stay in memory and are never included in diagnostics.
        if not credential:
            yield
            return
        digest = hashlib.sha256((credential + "\0" + endpoint).encode()).digest()
        key = (provider, digest)
        now = self._clock()
        with self._lock:
            self._blocked = {k: until for k, until in self._blocked.items() if until > now}
            blocked = key in self._blocked
        if blocked:
            raise ProviderAuthenticationUnavailable(provider, suppressed=True)
        try:
            yield
        except Exception as exc:
            # Do not guess authentication from provider body text or a 403
            # (which may be model/action permissions rather than a bad key).
            status = getattr(exc, "status_code", None)
            if status is None:
                status = getattr(getattr(exc, "response", None), "status_code", None)
            if status != 401:
                raise
            with self._lock:
                if key not in self._blocked and len(self._blocked) >= self._capacity:
                    oldest = min(self._blocked, key=self._blocked.get)
                    del self._blocked[oldest]
                self._blocked[key] = self._clock() + self._cooldown_s
            raise ProviderAuthenticationUnavailable(provider, suppressed=False) from None


provider_auth_backoff = ProviderAuthBackoff()


def provider_auth_scope(router: Any, provider: str, *, openai_client: Any = None) -> tuple[str, str]:
    """Use the actual OpenAI client key/endpoint; settings back other adapters."""
    settings = getattr(router, "settings", None)
    if provider == "openai":
        client = openai_client if openai_client is not None else getattr(router, "_openai", None)
        key = getattr(client, "api_key", None) or getattr(settings, "openai_api_key", "")
        return str(key or ""), str(getattr(client, "base_url", "") or "")
    if provider == "anthropic":
        return str(getattr(settings, "anthropic_api_key", "") or ""), ""
    # Match the exact key order used by provider_tool_router's Gemini adapter.
    key = getattr(settings, "gemini_key", None) or getattr(settings, "gemini_api_key", "")
    return str(key or ""), ""
