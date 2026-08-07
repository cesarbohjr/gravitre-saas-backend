"""Tier 1 voice adapters — ElevenLabs TTS + Deepgram STT (bolted onto chat).

No new reasoning path. STT returns plain text for the existing unified-turn
pipeline. TTS returns audio bytes for read-aloud.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings

# Scoped 3-voice set (ElevenLabs pre-made). Override via env.
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


class VoiceProviderError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


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
        "write_confirm_policy": "nl_yes_same_path_as_text",
        "write_confirm_note": (
            "Spoken confirmation becomes text and must hit the same awaiting_confirm "
            "classifier / execute endpoint as typed chat. Spoken yes alone does not "
            "bypass the write gate."
        ),
        "architecture": "tier1_bolted_on",
        "realtime_bar_ms": 300,
        "honest_expectation": (
            "Tier 1 is STT + model + TTS bolted onto text chat — not a sub-300ms "
            "realtime conversational agent."
        ),
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
        # Allow raw ElevenLabs voice id passthrough
        if len(key) >= 16:
            return key, key
        key = "rachel"
    return key, voices[key]["id"]


def synthesize_speech(
    settings: Settings,
    *,
    text: str,
    voice_key: str | None = None,
) -> tuple[bytes, str, dict[str, Any]]:
    api_key = (settings.elevenlabs_api_key or "").strip()
    if not api_key:
        raise VoiceProviderError("ElevenLabs TTS is not configured", status_code=503)
    clean = (text or "").strip()
    if not clean:
        raise VoiceProviderError("text is required", status_code=400)
    if len(clean) > 5000:
        clean = clean[:5000]
    key, voice_id = resolve_voice_id(settings, voice_key)
    model = (settings.elevenlabs_tts_model or "eleven_turbo_v2_5").strip()
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
        raise VoiceProviderError(
            f"ElevenLabs TTS failed: {resp.status_code}",
            status_code=502,
        )
    meta = {
        "provider": "elevenlabs",
        "voice_key": key,
        "voice_id": voice_id,
        "model": model,
        "bytes": len(resp.content),
        "content_type": "audio/mpeg",
    }
    return resp.content, "audio/mpeg", meta


def transcribe_audio(
    settings: Settings,
    *,
    audio_bytes: bytes,
    content_type: str = "audio/webm",
    filename: str = "audio.webm",
) -> tuple[str, dict[str, Any]]:
    api_key = (settings.deepgram_api_key or "").strip()
    if not api_key:
        raise VoiceProviderError("Deepgram STT is not configured", status_code=503)
    if not audio_bytes:
        raise VoiceProviderError("audio is required", status_code=400)
    model = (settings.deepgram_stt_model or "nova-2").strip()
    url = f"https://api.deepgram.com/v1/listen?model={model}&smart_format=true&punctuate=true"
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": content_type or "application/octet-stream",
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, content=audio_bytes)
    if resp.status_code >= 400:
        raise VoiceProviderError(
            f"Deepgram STT failed: {resp.status_code}",
            status_code=502,
        )
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
