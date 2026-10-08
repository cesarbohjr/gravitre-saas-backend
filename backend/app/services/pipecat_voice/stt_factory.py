"""Pipecat STT factory — Deepgram Flux primary, Nova-3 (or OpenAI) fallback.

Mirrors web_research Serper→Tavily discipline: primary first; on hard failure
log a visible warning and switch; never silent fallback.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.services.pipecat_voice.voice_keyterm_service import FLUX_TURN_PRESETS, resolve_flux_eot_settings

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


# Agent voice_profile.turn_sensitivity -> Flux turn preset. "normal" keeps the
# deployment's configured thresholds (voice_flux_turn_mode / eager / eot).
TURN_SENSITIVITY_TO_FLUX_PRESET: dict[str, str] = {
    "eager": "fast",
    "fast": "fast",
    "patient": "patient",
}


def normalize_stt_language(language: str | None) -> str | None:
    """Agent voice_profile.language -> Deepgram language code (None = provider default)."""
    value = str(language or "").strip().lower().replace("_", "-")
    if not value:
        return None
    return value[:8]


def is_english_language(language: str | None) -> bool:
    value = normalize_stt_language(language)
    return value is None or value == "en" or value.startswith("en-")


def _deepgram_language(value: str) -> Any:
    try:
        from pipecat.transcriptions.language import Language

        return Language(value)
    except Exception:  # noqa: BLE001
        return value


def build_pipecat_stt(
    settings: Any,
    *,
    provider: str | None = None,
    fallback_from: str | None = None,
    fallback_reason: str | None = None,
    keyterms: list[str] | None = None,
    language: str | None = None,
    turn_sensitivity: str | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Construct an STT service + honest metadata for session.ready / status.

    ``language`` / ``turn_sensitivity`` come from the agent's voice_profile.
    Flux is English-only, so a non-English agent language uses Nova-3 with that
    language instead. ``turn_sensitivity`` (eager/patient) picks a Flux turn preset.
    """
    choice = resolve_pipecat_stt_provider(settings, override=provider)
    dg_key = (getattr(settings, "deepgram_api_key", None) or "").strip()
    stt_language = normalize_stt_language(language)
    language_fallback = False
    if choice == STT_FLUX and not is_english_language(stt_language):
        choice = STT_NOVA3
        language_fallback = True

    if choice == STT_FLUX:
        if not dg_key:
            raise RuntimeError("DEEPGRAM_API_KEY required for Flux STT")
        from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService

        eager, eot = resolve_flux_eot_settings(settings)
        preset_key = TURN_SENSITIVITY_TO_FLUX_PRESET.get(str(turn_sensitivity or "").strip().lower())
        if preset_key and preset_key in FLUX_TURN_PRESETS:
            eager, eot = FLUX_TURN_PRESETS[preset_key]
        settings_kwargs: dict[str, Any] = {}
        if eager is not None:
            settings_kwargs["eager_eot_threshold"] = float(eager)
        if eot is not None:
            settings_kwargs["eot_threshold"] = float(eot)
        if keyterms:
            settings_kwargs["keyterm"] = list(keyterms)
        flux_settings = (
            DeepgramFluxSTTService.Settings(**settings_kwargs) if settings_kwargs else None
        )
        # With an eager threshold Flux reports "probably done" (EagerEndOfTurn)
        # ahead of the committed EndOfTurn. Pipecat drops that event unless
        # enable_eager_end_of_turn is on; on, it arrives as an
        # EagerTranscriptionFrame that starts the speculative answer early.
        # The pipeline passes its own user turn strategies, so this does not
        # change how turns are committed.
        stt = DeepgramFluxSTTService(
            api_key=dg_key,
            model="flux-general-en",
            should_interrupt=True,
            settings=flux_settings,
            enable_eager_end_of_turn=eager is not None,
        )
        meta = stt_meta(STT_FLUX, fallback_from=fallback_from, fallback_reason=fallback_reason)
        meta["stt_turn_detection"] = "flux_native_eot"
        meta["stt_eager_end_of_turn"] = eager is not None
        if preset_key:
            meta["stt_turn_sensitivity"] = preset_key
        if keyterms:
            meta["stt_keyterm_count"] = len(keyterms)
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

    nova_kwargs: dict[str, Any] = {"model": "nova-3-general", "interim_results": True}
    if stt_language:
        nova_kwargs["language"] = _deepgram_language(stt_language)
    stt = DeepgramSTTService(
        api_key=dg_key,
        settings=DeepgramSTTService.Settings(**nova_kwargs),
    )
    meta = stt_meta(STT_NOVA3, fallback_from=fallback_from, fallback_reason=fallback_reason)
    meta["stt_turn_detection"] = "aggregator_vad"
    if stt_language:
        meta["stt_language"] = stt_language
    if language_fallback:
        meta["stt_language_routed_from"] = STT_FLUX
    return stt, meta


def log_stt_fallback(*, primary: str, fallback: str, reason: str) -> None:
    """Visible fallback log — same class as web_research_fallback_to_tavily."""
    logger.warning(
        "voice_stt_fallback_to_%s primary=%s reason=%s",
        fallback,
        primary,
        reason[:200],
    )
