"""Classify ElevenLabs / Deepgram failures for monitoring — never collapse billing into outage."""
from __future__ import annotations

from typing import Any

from app.services.tier1_voice_service import VoiceProviderError


def classify_upstream_http_error(
    *,
    provider: str,
    status_code: int,
    body_text: str = "",
) -> VoiceProviderError:
    """Map provider HTTP status to a distinct Gravitre error.

    - 402 → HTTP 402 billing/quota (not a generic 502)
    - 401 → HTTP 401 auth
    - 429 → HTTP 429 rate limit
    - other 4xx/5xx → HTTP 502 service failure
    """
    snippet = (body_text or "").strip()[:400]
    code = int(status_code)
    if code == 402:
        return VoiceProviderError(
            (
                f"{provider} voice service unavailable: billing issue "
                f"(insufficient credits or payment required). Upstream 402."
                + (f" Detail: {snippet}" if snippet else "")
            ),
            status_code=402,
            error_class="billing",
            provider=provider,
            upstream_status=402,
            provider_detail=snippet,
        )
    if code == 401:
        return VoiceProviderError(
            f"{provider} authentication failed (invalid or revoked API key).",
            status_code=401,
            error_class="auth",
            provider=provider,
            upstream_status=401,
            provider_detail=snippet,
        )
    if code == 429:
        return VoiceProviderError(
            f"{provider} rate limit exceeded. Retry shortly.",
            status_code=429,
            error_class="rate_limit",
            provider=provider,
            upstream_status=429,
            provider_detail=snippet,
        )
    return VoiceProviderError(
        f"{provider} failed: {code}" + (f" — {snippet}" if snippet else ""),
        status_code=502,
        error_class="service_failure",
        provider=provider,
        upstream_status=code,
        provider_detail=snippet,
    )


def error_public_payload(exc: VoiceProviderError) -> dict[str, Any]:
    return {
        "detail": str(exc),
        "error_class": getattr(exc, "error_class", None) or "service_failure",
        "provider": getattr(exc, "provider", None),
        "upstream_status": getattr(exc, "upstream_status", None),
        "billing_issue": getattr(exc, "error_class", None) == "billing",
    }
