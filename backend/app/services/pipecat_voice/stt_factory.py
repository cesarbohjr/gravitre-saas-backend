"""Pipecat STT factory — Deepgram Flux primary, Nova-3 (or OpenAI) fallback.

Mirrors web_research Serper→Tavily discipline: primary first; on hard failure
log a visible warning and switch; never silent fallback.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

STT_FLUX = "flux"
STT_NOVA3 = "nova3"
STT_OPENAI = "openai"


def resolve_pipecat_stt_provider(settings: Any, *, override: str | None = None) -> str:
    raw = (override or getattr(settings, "voice_pipecat_stt", None) or STT_FLUX)
    choice = str(raw).strip().lower()
    if choice in {STT_FLUX, "deepgram_flux", "flux-general-en"}:
        return STT_FLUX
    if choice in {STT_NOVA3, "nova-3", "nova-3-general", "deepgram_nova3"}:
        return STT_NOVA3
    if choice in {STT_OPENAI, "whisper", "openai_stt"}:
        return STT_OPENAI
    return STT_FLUX


def resolve_pipecat_stt_fallback(settings: Any) -> str:
    raw = getattr(settings, "voice_pipecat_stt_fallback", None) or STT_NOVA3
    choice = str(raw).strip().lower()
    if choice in {STT_OPENAI, "whisper", "openai_stt"}:
        return STT_OPENAI
    return STT_NOVA3


def stt_meta(provider: str, *, fallback_from: str | None = None, fallback_reason: str | None = None) -> dict[str, Any]:
    if provider == STT_FLUX:
        model = "flux-general-en"
        label = "deepgram_flux"
    elif provider == STT_OPENAI:
        model = "whisper-1"
        label = "openai_whisper"
    else:
        model = "nova-3-general"
        label = "deepgram_nova3"
    out: dict[str, Any] = {
        "stt_provider": label,
        "stt_model": model,
        "stt_provider_key": provider,
    }
    if fallback_from:
        out["stt_fallback_from"] = fallback_from
        out["stt_fallback_reason"] = fallback_reason or "primary_failed"
    return out


def build_pipecat_stt(
    settings: Any,
    *,
    provider: str | None = None,
    fallback_from: str | None = None,
    fallback_reason: str | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Construct an STT service + honest metadata for session.ready / status."""
    choice = resolve_pipecat_stt_provider(settings, override=provider)
    dg_key = (getattr(settings, "deepgram_api_key", None) or "").strip()

    if choice == STT_FLUX:
        if not dg_key:
            raise RuntimeError("DEEPGRAM_API_KEY required for Flux STT")
        from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService

        eager = getattr(settings, "voice_pipecat_flux_eager_eot", None)
        eot = getattr(settings, "voice_pipecat_flux_eot", None)
        settings_kwargs: dict[str, Any] = {}
        if eager is not None:
            settings_kwargs["eager_eot_threshold"] = float(eager)
        if eot is not None:
            settings_kwargs["eot_threshold"] = float(eot)
        flux_settings = (
            DeepgramFluxSTTService.Settings(**settings_kwargs) if settings_kwargs else None
        )
        stt = DeepgramFluxSTTService(
            api_key=dg_key,
            model="flux-general-en",
            should_interrupt=True,
            settings=flux_settings,
        )
        meta = stt_meta(STT_FLUX, fallback_from=fallback_from, fallback_reason=fallback_reason)
        meta["stt_turn_detection"] = "flux_native_eot"
        return stt, meta

    if choice == STT_OPENAI:
        oai = (getattr(settings, "openai_api_key", None) or "").strip()
        if not oai:
            raise RuntimeError("OPENAI_API_KEY required for OpenAI STT fallback")
        from pipecat.services.openai.stt import OpenAISTTService

        stt = OpenAISTTService(api_key=oai)
        meta = stt_meta(STT_OPENAI, fallback_from=fallback_from, fallback_reason=fallback_reason)
        meta["stt_turn_detection"] = "aggregator_vad"
        return stt, meta

    # nova3
    if not dg_key:
        raise RuntimeError("DEEPGRAM_API_KEY required for Nova-3 STT")
    from pipecat.services.deepgram.stt import DeepgramSTTService

    stt = DeepgramSTTService(
        api_key=dg_key,
        settings=DeepgramSTTService.Settings(
            model="nova-3-general",
            interim_results=True,
        ),
    )
    meta = stt_meta(STT_NOVA3, fallback_from=fallback_from, fallback_reason=fallback_reason)
    meta["stt_turn_detection"] = "aggregator_vad"
    return stt, meta


def log_stt_fallback(*, primary: str, fallback: str, reason: str) -> None:
    """Visible fallback log — same class as web_research_fallback_to_tavily."""
    logger.warning(
        "voice_stt_fallback_to_%s primary=%s reason=%s",
        fallback,
        primary,
        reason[:200],
    )
