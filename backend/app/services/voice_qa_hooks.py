"""QA-only hooks for deterministic voice/TTS error verification.

Active only when ``unified_turn_qa_hooks_enabled`` is true AND a per-request
header (or ``VOICE_QA_FORCE_ERROR`` env) is set — no effect on normal traffic.
"""
from __future__ import annotations

import os
from typing import Any

from app.services.tier1_voice_service import VoiceProviderError

QA_FORCE_VOICE_ERROR_HEADER = "X-Gravitre-QA-Force-Voice-Error"

_ALLOWED = frozenset({"billing", "service_failure", "auth", "rate_limit"})


def resolve_qa_force_voice_error(
    settings: Any,
    *,
    header_value: str | None = None,
) -> str | None:
    if not getattr(settings, "unified_turn_qa_hooks_enabled", False):
        return None
    raw = (header_value or "").strip() or (os.environ.get("VOICE_QA_FORCE_ERROR") or "").strip()
    if not raw:
        return None
    token = raw.lower()
    if token not in _ALLOWED:
        raise ValueError(f"unknown QA force voice error: {raw}")
    return token


def forced_voice_provider_error(error_class: str) -> VoiceProviderError:
    """Synthetic provider error matching production classification shape."""
    token = (error_class or "").strip().lower()
    if token == "billing":
        return VoiceProviderError(
            (
                "ElevenLabs voice service unavailable: billing issue "
                "(insufficient credits or payment required). Upstream 402. "
                "Detail: qa_force_voice_error=billing"
            ),
            status_code=402,
            error_class="billing",
            provider="ElevenLabs",
            upstream_status=402,
            provider_detail="qa_force_voice_error=billing",
        )
    if token == "auth":
        return VoiceProviderError(
            "ElevenLabs authentication failed (invalid or revoked API key).",
            status_code=401,
            error_class="auth",
            provider="ElevenLabs",
            upstream_status=401,
            provider_detail="qa_force_voice_error=auth",
        )
    if token == "rate_limit":
        return VoiceProviderError(
            "ElevenLabs rate limit exceeded. Retry shortly.",
            status_code=429,
            error_class="rate_limit",
            provider="ElevenLabs",
            upstream_status=429,
            provider_detail="qa_force_voice_error=rate_limit",
        )
    return VoiceProviderError(
        "ElevenLabs failed: 500 — qa_force_voice_error=service_failure",
        status_code=502,
        error_class="service_failure",
        provider="ElevenLabs",
        upstream_status=500,
        provider_detail="qa_force_voice_error=service_failure",
    )
