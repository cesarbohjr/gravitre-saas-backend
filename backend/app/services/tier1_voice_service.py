"""Voice adapters — ElevenLabs TTS + Deepgram STT.

HTTP batch paths remain for read-aloud / mic-stop. Streaming paths feed the
realtime voice session (Deepgram live WS + ElevenLabs stream).
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

import httpx

from app.config import Settings

# Process-scoped ElevenLabs HTTP client — reuse TCP/TLS across TTS calls so
# HTTP duplex TTFA does not pay a fresh connect on every speakable chunk.
# Pipecat already warms a WS; this is the equivalent for the HTTP stream path.
_elevenlabs_client: httpx.Client | None = None
_elevenlabs_client_lock = threading.Lock()


def _get_elevenlabs_http_client(timeout: httpx.Timeout | float) -> httpx.Client:
    global _elevenlabs_client
    with _elevenlabs_client_lock:
        if _elevenlabs_client is None or _elevenlabs_client.is_closed:
            _elevenlabs_client = httpx.Client(
                timeout=timeout,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return _elevenlabs_client


def reset_elevenlabs_http_client_for_tests() -> None:
    """Close and clear the shared client (unit tests only)."""
    global _elevenlabs_client
    with _elevenlabs_client_lock:
        if _elevenlabs_client is not None and not _elevenlabs_client.is_closed:
            _elevenlabs_client.close()
        _elevenlabs_client = None

# Shortcut keys (env-overridable). Full library is voice_library_service.
# Default product voice is Sarah (warmer / more natural than Rachel demo).
DEFAULT_VOICES: dict[str, dict[str, str]] = {
    "sarah": {
        "id": "EXAVITQu4vr4xnSDxMaL",
        "label": "Sarah",
        "description": "Soft, reassuring, natural conversational",
    },
    "rachel": {
        "id": "21m00Tcm4TlvDq8ikWAM",
        "label": "Rachel",
        "description": "Clear professional female",
    },
    "adam": {
        "id": "pNInz6obpgDQGcFmaJgB",
        "label": "Adam",
        "description": "Clear professional male",
    },
    "josh": {
        "id": "TxGEqnHWrfWFTfGW9XjX",
        "label": "Josh",
        "description": "Conversational male",
    },
    "eric": {
        "id": "cjVigY5qzO86Huf0OWal",
        "label": "Eric",
        "description": "Friendly midwestern American",
    },
}

# Honest latency targets (not marketing sub-300ms claims).
LATENCY_TARGETS_MS = {
    "deepgram_stt_partial_ms": (150, 300),
    "elevenlabs_flash_ttfb_ms": (75, 255),
    "end_to_end_feels_human_ms": (700, 900),
}

# Medium expressiveness for live conversational TTS (HTTP + Pipecat).
# Lower stability + moderate style = more natural variation than the old flat demo defaults.
CONVERSATIONAL_VOICE_SETTINGS: dict[str, float | bool] = {
    "stability": 0.25,
    "similarity_boost": 0.75,
    "style": 0.4,
    "use_speaker_boost": True,
}


class VoiceProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_class: str | None = None,
        provider: str | None = None,
        upstream_status: int | None = None,
        provider_detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_class = error_class or (
            "billing"
            if status_code == 402
            else "auth"
            if status_code == 401
            else "rate_limit"
            if status_code == 429
            else "service_failure"
        )
        self.provider = provider
        self.upstream_status = upstream_status
        self.provider_detail = provider_detail


def _raise_upstream(provider: str, resp: httpx.Response) -> None:
    from app.services.voice_provider_errors import classify_upstream_http_error

    raise classify_upstream_http_error(
        provider=provider,
        status_code=resp.status_code,
        body_text=resp.text or "",
    )


def _pipecat_import_available() -> bool:
    try:
        import pipecat  # noqa: F401

        return True
    except ImportError:
        return False


def _pipecat_ws_hint(settings: Settings) -> str:
    """Absolute wss/ws base for browser clients (no path). Empty when unknown."""
    raw = (getattr(settings, "api_public_url", None) or "").strip().rstrip("/")
    if not raw:
        raw = "https://api.gravitre.app"
    if raw.startswith("https://"):
        return "wss://" + raw[len("https://") :]
    if raw.startswith("http://"):
        return "ws://" + raw[len("http://") :]
    if raw.startswith("wss://") or raw.startswith("ws://"):
        return raw
    return f"wss://{raw}"


def _pipecat_stt_status(settings: Settings) -> dict[str, Any]:
    """Honest STT primary/fallback advertisement for /api/voice/status."""
    try:
        from app.services.pipecat_voice.stt_factory import (
            resolve_pipecat_stt_fallback,
            resolve_pipecat_stt_provider,
            stt_meta,
        )

        primary = resolve_pipecat_stt_provider(settings)
        fallback = resolve_pipecat_stt_fallback(settings)
        meta = stt_meta(primary)
        return {
            **meta,
            "fallback_enabled": bool(getattr(settings, "voice_pipecat_stt_fallback_enabled", True)),
            "fallback_provider": stt_meta(fallback).get("stt_provider"),
            "fallback_key": fallback,
        }
    except Exception:  # noqa: BLE001
        return {
            "stt_provider": "deepgram_flux",
            "stt_model": "flux-general-en",
            "fallback_enabled": True,
            "fallback_provider": "deepgram_nova3",
        }


def voice_status(settings: Settings) -> dict[str, Any]:
    voices = _resolved_voices(settings)
    return {
        "tts_provider": "elevenlabs" if (settings.elevenlabs_api_key or "").strip() else None,
        "stt_provider": "deepgram" if (settings.deepgram_api_key or "").strip() else None,
        "tts_enabled": bool((settings.elevenlabs_api_key or "").strip()),
        "stt_enabled": bool((settings.deepgram_api_key or "").strip()),
        "voices": [
            {"key": k, "id": v["id"], "label": v["label"], "description": v["description"]}
            for k, v in voices.items()
        ],
        "default_voice": settings.elevenlabs_default_voice or "sarah",
        "default_tts_model": (settings.elevenlabs_tts_model or "eleven_flash_v2_5").strip(),
        "write_confirm_policy": "nl_yes_same_path_as_text",
        "write_confirm_note": (
            "Spoken confirmation becomes text and must hit the same awaiting_confirm "
            "classifier / execute endpoint as typed chat. Spoken yes alone does not "
            "bypass the write gate."
        ),
        "architecture": "streaming_voice_session_over_unified_turn",
        "pipecat_enabled": bool(getattr(settings, "voice_pipecat_enabled", False)),
        "pipecat_available": _pipecat_import_available(),
        "pipecat_ws_path": "/api/voice/pipecat/ws",
        "pipecat_ws_hint": _pipecat_ws_hint(settings),
        "pipecat_architecture": (
            "pipecat_deepgram_cognitive_elevenlabs"
            if bool(getattr(settings, "voice_pipecat_enabled", False))
            else None
        ),
        "default_orchestration": (
            "pipecat"
            if bool(getattr(settings, "voice_pipecat_enabled", False))
            else "http_session_turn"
        ),
        "pipecat_ws_clients_accepted": bool(getattr(settings, "voice_pipecat_enabled", False)),
        "pipecat_stt": _pipecat_stt_status(settings),
        "pipecat_tts": {
            "model": (settings.elevenlabs_tts_model or "eleven_flash_v2_5").strip(),
            "transport": "websocket" if bool(getattr(settings, "voice_pipecat_enabled", False)) else "http_stream",
        },
        "realtime_bar_ms": 300,
        "latency_targets_ms": LATENCY_TARGETS_MS,
        "honest_expectation": (
            "Honest end-to-end target ~700–900ms (feels human). Deepgram STT ~150–300ms; "
            "ElevenLabs Flash v2.5 first-byte ~75–255ms. Not a sub-300ms claim."
        ),
        "entitlement": {
            "model": "plan_included",
            "org_toggle": "subscriptions.voice_enabled",
            "meson_purchase_gate": False,
            "use_vs_configure": (
                "B1: with org voice ON (default), Lite seats USE voice mode on agents "
                "assigned to their department; CONFIGURE (assign/change voice, turn-taking, "
                "Voice Design) requires full or department-manager seat."
            ),
        },
        "error_classes": ["billing", "auth", "rate_limit", "service_failure"],
        "entitlement_decision_needed": False,
        "phase1_mic_capture": {
            "agc_v2": bool(getattr(settings, "voice_agc_v2", False)),
            "mic_telemetry_v1": bool(getattr(settings, "voice_mic_telemetry_v1", False)),
            "preroll_v2": bool(getattr(settings, "voice_preroll_v2", False)),
            "preroll_ms": int(getattr(settings, "voice_preroll_ms", 300) or 300),
            "mic_selector_v1": bool(getattr(settings, "voice_mic_selector_v1", False)),
            "near_far_v1": bool(getattr(settings, "voice_near_far_v1", False)),
        },
        "phase2_echo_noise": {
            "mic_silent_tap_v2": bool(getattr(settings, "voice_mic_silent_tap_v2", True)),
            "echo_test_mode": bool(getattr(settings, "voice_echo_test_mode", False)),
            "krisp_enabled": bool(getattr(settings, "voice_krisp", False)),
            "krisp_configured": bool(
                (getattr(settings, "krisp_viva_filter_model_path", None) or "").strip()
            ),
        },
        "phase3_turn_stt": _phase3_turn_stt_status(settings),
        "phase4_latency": _phase4_latency_status(settings),
        "phase5_conversational_polish": _phase5_polish_status(settings),
    }


def _phase5_polish_status(settings: Settings) -> dict[str, Any]:
    from app.services.pipecat_voice.voice_conversational_polish import (
        resolve_conversational_polish_flags,
    )

    return resolve_conversational_polish_flags(settings)


def _phase4_latency_status(settings: Settings) -> dict[str, Any]:
    from app.services.pipecat_voice.voice_latency_tuning import (
        TTS_AB_EVAL_MODELS,
        resolve_voice_speculative_tuning,
        resolve_voice_tts_ab_eval,
        resolve_voice_tts_chunk_tuning,
    )

    spec = resolve_voice_speculative_tuning(settings)
    chunk = resolve_voice_tts_chunk_tuning(settings)
    ab = resolve_voice_tts_ab_eval(settings)
    return {
        "speculative_v2": spec.v2_enabled,
        "speculative_min_chars": spec.min_chars,
        "speculative_prefix_adopt": spec.prefix_adopt,
        "speculative_prefix_max_words": spec.prefix_max_extra_words,
        "tts_chunk_v2": chunk.v2_enabled,
        "tts_chunk_min_chars": chunk.min_chars,
        "tts_ab_v1": ab.enabled,
        "tts_ab_model": ab.model,
        "tts_ab_allowed_models": sorted(TTS_AB_EVAL_MODELS),
    }


def _phase3_turn_stt_status(settings: Settings) -> dict[str, Any]:
    from app.services.pipecat_voice.voice_keyterm_service import (
        FLUX_TURN_PRESETS,
        resolve_flux_eot_settings,
        resolve_flux_turn_mode_label,
    )

    mode = resolve_flux_turn_mode_label(settings)
    eager, eot = resolve_flux_eot_settings(settings)
    return {
        "keyterms_v1": bool(getattr(settings, "voice_keyterms_v1", False)),
        "keyterms_max": int(getattr(settings, "voice_keyterms_max", 50) or 50),
        "flux_turn_mode": mode,
        "flux_turn_mode_valid": mode in FLUX_TURN_PRESETS if mode else None,
        "flux_eager_eot": eager,
        "flux_eot": eot,
    }


def _resolved_voices(settings: Settings) -> dict[str, dict[str, str]]:
    out = {k: dict(v) for k, v in DEFAULT_VOICES.items()}
    overrides = {
        "sarah": settings.elevenlabs_voice_sarah,
        "rachel": settings.elevenlabs_voice_rachel,
        "adam": settings.elevenlabs_voice_adam,
        "josh": settings.elevenlabs_voice_josh,
        "eric": settings.elevenlabs_voice_eric,
    }
    for key, vid in overrides.items():
        if (vid or "").strip():
            out[key]["id"] = vid.strip()
    return out


def resolve_voice_id(settings: Settings, voice_key: str | None) -> tuple[str, str]:
    voices = _resolved_voices(settings)
    key = (voice_key or settings.elevenlabs_default_voice or "sarah").strip().lower()
    if key not in voices:
        if len(key) >= 16:
            return key, key
        key = "sarah"
    return key, voices[key]["id"]


def synthesize_speech(
    settings: Settings,
    *,
    text: str,
    voice_key: str | None = None,
    model_id: str | None = None,
) -> tuple[bytes, str, dict[str, Any]]:
    api_key = (settings.elevenlabs_api_key or "").strip()
    if not api_key:
        raise VoiceProviderError(
            "ElevenLabs TTS is not configured",
            status_code=503,
            error_class="not_configured",
            provider="elevenlabs",
        )
    clean = (text or "").strip()
    if not clean:
        raise VoiceProviderError("text is required", status_code=400, error_class="validation")
    if len(clean) > 5000:
        clean = clean[:5000]
    key, voice_id = resolve_voice_id(settings, voice_key)
    model = (model_id or settings.elevenlabs_tts_model or "eleven_flash_v2_5").strip()
    # Prefer Flash v2.5 naming; accept legacy turbo alias.
    if model in {"eleven_turbo_v2_5", "eleven_turbo_v2"}:
        model = "eleven_flash_v2_5"
    # Non-stream path also needs an explicit enum — bare mpeg is rejected (403).
    fmt, accept = normalize_elevenlabs_output_format("mp3_44100_128")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format={fmt}"
    headers = {
        "xi-api-key": api_key,
        "Accept": accept,
        "Content-Type": "application/json",
    }
    body = {
        "text": clean,
        "model_id": model,
        "voice_settings": dict(CONVERSATIONAL_VOICE_SETTINGS),
    }
    client = _get_elevenlabs_http_client(60.0)
    resp = client.post(url, headers=headers, json=body)
    if resp.status_code >= 400:
        _raise_upstream("ElevenLabs", resp)
    meta = {
        "provider": "elevenlabs",
        "voice_key": key,
        "voice_id": voice_id,
        "model": model,
        "bytes": len(resp.content),
        "content_type": "audio/mpeg",
    }
    return resp.content, "audio/mpeg", meta


def normalize_elevenlabs_output_format(output_format: str | None) -> tuple[str, str]:
    """Map legacy / alias formats to ElevenLabs-accepted ``output_format`` values.

    ElevenLabs rejects bare ``mpeg`` (403 invalid_output_format). Browser duplex
    and batch TTS must use an explicit mp3_* enum; PSTN uses ``ulaw_8000``.
    Returns ``(api_output_format, http_accept)``.
    """
    raw = (output_format or "mp3_44100_128").strip().lower()
    if raw in {"ulaw", "ulaw_8000", "mulaw", "mulaw_8000"}:
        return "ulaw_8000", "audio/basic"
    if raw in {"alaw", "alaw_8000"}:
        return "alaw_8000", "audio/basic"
    # Legacy Accept-style / shorthand aliases → concrete mp3 enum.
    if raw in {"mpeg", "mp3", "audio/mpeg", "mp3_44100_128"}:
        return "mp3_44100_128", "audio/mpeg"
    if raw.startswith("mp3_") or raw.startswith("opus_") or raw.startswith("pcm_") or raw.startswith("m4a_"):
        accept = "audio/basic" if raw.startswith("pcm_") else "audio/mpeg"
        return raw, accept
    # Unknown → safest browser default (never send bare "mpeg").
    return "mp3_44100_128", "audio/mpeg"


def synthesize_speech_stream(
    settings: Settings,
    *,
    text: str,
    voice_key: str | None = None,
    model_id: str | None = None,
    output_format: str = "mp3_44100_128",
) -> Iterator[bytes]:
    """Stream audio chunks from ElevenLabs as soon as first byte is available.

    output_format: ``mp3_44100_128`` (browser; legacy ``mpeg`` alias ok) or
    ``ulaw_8000`` (Twilio Media Streams).
    """
    api_key = (settings.elevenlabs_api_key or "").strip()
    if not api_key:
        raise VoiceProviderError(
            "ElevenLabs TTS is not configured",
            status_code=503,
            error_class="not_configured",
            provider="elevenlabs",
        )
    clean = (text or "").strip()
    if not clean:
        raise VoiceProviderError("text is required", status_code=400, error_class="validation")
    if len(clean) > 5000:
        clean = clean[:5000]
    _key, voice_id = resolve_voice_id(settings, voice_key)
    model = (model_id or settings.elevenlabs_tts_model or "eleven_flash_v2_5").strip()
    if model in {"eleven_turbo_v2_5", "eleven_turbo_v2"}:
        model = "eleven_flash_v2_5"
    fmt, accept = normalize_elevenlabs_output_format(output_format)
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream?output_format={fmt}"
    headers = {
        "xi-api-key": api_key,
        "Accept": accept,
        "Content-Type": "application/json",
    }
    body = {
        "text": clean,
        "model_id": model,
        "voice_settings": dict(CONVERSATIONAL_VOICE_SETTINGS),
        "optimize_streaming_latency": 3,
    }
    timeout = httpx.Timeout(connect=5.0, read=20.0, write=20.0, pool=10.0)
    client = _get_elevenlabs_http_client(timeout)
    with client.stream("POST", url, headers=headers, json=body) as resp:
        if resp.status_code >= 400:
            # Need body for classification
            _ = resp.read()
            _raise_upstream("ElevenLabs", resp)
        for chunk in resp.iter_bytes(chunk_size=2048):
            if chunk:
                yield chunk


def transcribe_audio(
    settings: Settings,
    *,
    audio_bytes: bytes,
    content_type: str = "audio/webm",
    filename: str = "audio.webm",
) -> tuple[str, dict[str, Any]]:
    api_key = (settings.deepgram_api_key or "").strip()
    if not api_key:
        raise VoiceProviderError(
            "Deepgram STT is not configured",
            status_code=503,
            error_class="not_configured",
            provider="deepgram",
        )
    if not audio_bytes:
        raise VoiceProviderError("audio is required", status_code=400, error_class="validation")
    model = (settings.deepgram_stt_model or "nova-2").strip()
    url = (
        f"https://api.deepgram.com/v1/listen?model={model}"
        "&smart_format=true&punctuate=true&utterances=true&vad_events=true"
    )
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": content_type or "application/octet-stream",
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, content=audio_bytes)
    if resp.status_code >= 400:
        _raise_upstream("Deepgram", resp)
    data = resp.json()
    transcript = ""
    try:
        transcript = (
            data["results"]["channels"][0]["alternatives"][0].get("transcript") or ""
        ).strip()
    except (KeyError, IndexError, TypeError):
        transcript = ""
    meta = {
        "provider": "deepgram",
        "model": model,
        "filename": filename,
        "audio_bytes": len(audio_bytes),
        "content_type": content_type,
    }
    return transcript, meta


def deepgram_live_ws_url(settings: Settings, *, pstn: bool = False) -> str:
    """WebSocket URL for streaming STT with VAD events.

    Browser/desktop uses linear16 @ 16 kHz. PSTN (Twilio Media Streams) uses
    mulaw @ 8 kHz — same Deepgram model, no second STT vendor decision.
    """
    model = (settings.deepgram_stt_model or "nova-2").strip()
    if pstn:
        encoding = "mulaw"
        sample_rate = 8000
    else:
        encoding = "linear16"
        sample_rate = 16000
    return (
        f"wss://api.deepgram.com/v1/listen?model={model}"
        f"&encoding={encoding}&sample_rate={sample_rate}&channels=1"
        "&interim_results=true&punctuate=true&smart_format=true"
        "&vad_events=true&utterance_end_ms=1000&endpointing=300"
    )


def mint_deepgram_live_credentials(
    settings: Settings,
    *,
    ttl_seconds: int = 60,
    pstn: bool = False,
) -> dict[str, Any]:
    """Mint a short-lived Deepgram JWT for WebSocket STT (browser or PSTN bridge)."""
    key = (settings.deepgram_api_key or "").strip()
    if not key:
        raise VoiceProviderError(
            "Deepgram API key not configured",
            status_code=503,
            error_class="not_configured",
            provider="deepgram",
        )
    ttl = max(15, min(int(ttl_seconds or 60), 120))
    url = deepgram_live_ws_url(settings, pstn=pstn)
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.post(
                "https://api.deepgram.com/v1/auth/grant",
                headers={
                    "Authorization": f"Token {key}",
                    "Content-Type": "application/json",
                },
                json={"ttl_seconds": ttl},
            )
    except httpx.HTTPError as exc:
        raise VoiceProviderError(
            f"Deepgram grant failed: {exc}",
            status_code=502,
            error_class="service_failure",
            provider="deepgram",
        ) from exc
    if resp.status_code >= 400:
        raise VoiceProviderError(
            f"Deepgram grant HTTP {resp.status_code}",
            status_code=502,
            error_class="service_failure",
            provider="deepgram",
            upstream_status=resp.status_code,
        )
    data = resp.json() if resp.content else {}
    access_token = str(data.get("access_token") or data.get("token") or "").strip()
    if not access_token:
        # Fallback: some projects lack grant — do not return the master key to browsers.
        raise VoiceProviderError(
            "Deepgram temporary token unavailable for this project",
            status_code=503,
            error_class="not_configured",
            provider="deepgram",
        )
    encoding = "mulaw" if pstn else "linear16"
    sample_rate = 8000 if pstn else 16000
    return {
        "ws_url": url,
        "access_token": access_token,
        "authorization": f"Bearer {access_token}",
        "expires_in_seconds": int(data.get("expires_in") or ttl),
        "encoding": encoding,
        "sample_rate": sample_rate,
        "provider": "deepgram",
        "pstn": pstn,
        "pipeline": "live_ws_into_session_turn",
    }
