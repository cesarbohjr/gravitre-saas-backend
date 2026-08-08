"""Voice adapters — ElevenLabs TTS + Deepgram STT.

HTTP batch paths remain for read-aloud / mic-stop. Streaming paths feed the
realtime voice session (Deepgram live WS + ElevenLabs stream).
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx

from app.config import Settings

# Legacy 3-voice shortcuts (env-overridable). Full library is voice_library_service.
DEFAULT_VOICES: dict[str, dict[str, str]] = {
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
}

# Honest latency targets (not marketing sub-300ms claims).
LATENCY_TARGETS_MS = {
    "deepgram_stt_partial_ms": (150, 300),
    "elevenlabs_flash_ttfb_ms": (75, 255),
    "end_to_end_feels_human_ms": (700, 900),
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
        "default_voice": settings.elevenlabs_default_voice or "rachel",
        "default_tts_model": (settings.elevenlabs_tts_model or "eleven_flash_v2_5").strip(),
        "write_confirm_policy": "nl_yes_same_path_as_text",
        "write_confirm_note": (
            "Spoken confirmation becomes text and must hit the same awaiting_confirm "
            "classifier / execute endpoint as typed chat. Spoken yes alone does not "
            "bypass the write gate."
        ),
        "architecture": "streaming_voice_session_over_unified_turn",
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
    }


def _resolved_voices(settings: Settings) -> dict[str, dict[str, str]]:
    out = {k: dict(v) for k, v in DEFAULT_VOICES.items()}
    overrides = {
        "rachel": settings.elevenlabs_voice_rachel,
        "adam": settings.elevenlabs_voice_adam,
        "josh": settings.elevenlabs_voice_josh,
    }
    for key, vid in overrides.items():
        if (vid or "").strip():
            out[key]["id"] = vid.strip()
    return out


def resolve_voice_id(settings: Settings, voice_key: str | None) -> tuple[str, str]:
    voices = _resolved_voices(settings)
    key = (voice_key or settings.elevenlabs_default_voice or "rachel").strip().lower()
    if key not in voices:
        if len(key) >= 16:
            return key, key
        key = "rachel"
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
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    body = {
        "text": clean,
        "model_id": model,
        "voice_settings": {"stability": 0.4, "similarity_boost": 0.75},
    }
    with httpx.Client(timeout=60.0) as client:
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


def synthesize_speech_stream(
    settings: Settings,
    *,
    text: str,
    voice_key: str | None = None,
    model_id: str | None = None,
) -> Iterator[bytes]:
    """Stream MPEG chunks from ElevenLabs as soon as first byte is available."""
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
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    headers = {
        "xi-api-key": api_key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    body = {
        "text": clean,
        "model_id": model,
        "voice_settings": {"stability": 0.4, "similarity_boost": 0.75},
        "optimize_streaming_latency": 3,
    }
    with httpx.Client(timeout=60.0) as client:
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


def deepgram_live_ws_url(settings: Settings) -> str:
    """WebSocket URL for streaming STT with VAD events."""
    model = (settings.deepgram_stt_model or "nova-2").strip()
    return (
        f"wss://api.deepgram.com/v1/listen?model={model}"
        "&encoding=linear16&sample_rate=16000&channels=1"
        "&interim_results=true&punctuate=true&smart_format=true"
        "&vad_events=true&utterance_end_ms=1000&endpointing=300"
    )
