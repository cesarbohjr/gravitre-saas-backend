"""ElevenLabs Voice Design v3 (text-to-voice) — full custom voice path."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.services.tier1_voice_service import VoiceProviderError, _raise_upstream

EXAMPLE_DESCRIPTIONS = [
    {
        "title": "Calm ops lead",
        "voice_description": (
            "A calm American woman in her 30s, clear and direct, warm but not bubbly, "
            "steady pacing suitable for business operations updates."
        ),
        "guided": {
            "gender": "female",
            "age": "30s",
            "accent": "american",
            "tone": "calm professional",
            "pace": "steady",
        },
    },
    {
        "title": "Friendly support",
        "voice_description": (
            "A friendly midwestern American man, reassuring and patient, slightly casual, "
            "good for customer support without sounding scripted."
        ),
        "guided": {
            "gender": "male",
            "age": "30s",
            "accent": "american midwest",
            "tone": "friendly reassuring",
            "pace": "moderate",
        },
    },
    {
        "title": "Polished British advisor",
        "voice_description": (
            "A polished British woman, articulate and composed, lightly formal, "
            "suited to executive briefings and finance summaries."
        ),
        "guided": {
            "gender": "female",
            "age": "40s",
            "accent": "british rp",
            "tone": "polished formal",
            "pace": "measured",
        },
    },
]


def compose_voice_description(
    *,
    freeform: str | None = None,
    guided: dict[str, Any] | None = None,
) -> str:
    if (freeform or "").strip():
        return freeform.strip()
    g = guided or {}
    parts = [
        str(g.get("gender") or "").strip(),
        str(g.get("age") or "").strip(),
        str(g.get("accent") or "").strip(),
        str(g.get("tone") or "").strip(),
        str(g.get("pace") or "").strip(),
        str(g.get("extra") or "").strip(),
    ]
    bits = [p for p in parts if p]
    if not bits:
        raise VoiceProviderError(
            "voice_description or guided fields are required",
            status_code=400,
            error_class="validation",
        )
    return (
        f"A {', '.join(bits[:3])} voice" + (f", {', '.join(bits[3:])}" if len(bits) > 3 else "")
        + ". Natural conversational delivery for business dialogue."
    )


def design_custom_voice(
    settings: Settings,
    *,
    voice_description: str | None = None,
    guided: dict[str, Any] | None = None,
    model_id: str = "eleven_ttv_v3",
    auto_generate_text: bool = True,
    text: str | None = None,
    guidance_scale: float = 5.0,
    loudness: float = 0.5,
    seed: int | None = None,
    should_enhance: bool = True,
) -> dict[str, Any]:
    """POST /v1/text-to-voice/design — returns previewable generated_voice_ids."""
    api_key = (settings.elevenlabs_api_key or "").strip()
    if not api_key:
        raise VoiceProviderError(
            "ElevenLabs TTS is not configured",
            status_code=503,
            error_class="not_configured",
            provider="elevenlabs",
        )
    description = compose_voice_description(freeform=voice_description, guided=guided)
    body: dict[str, Any] = {
        "voice_description": description,
        "model_id": model_id or "eleven_ttv_v3",
        "auto_generate_text": bool(auto_generate_text),
        "guidance_scale": float(guidance_scale),
        "loudness": float(loudness),
        "should_enhance": bool(should_enhance),
    }
    if text and len(text.strip()) >= 100:
        body["text"] = text.strip()[:1000]
        body["auto_generate_text"] = False
    if seed is not None:
        body["seed"] = int(seed)
    url = "https://api.elevenlabs.io/v1/text-to-voice/design"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, headers=headers, json=body)
    if resp.status_code >= 400:
        _raise_upstream("ElevenLabs", resp)
    data = resp.json()
    previews = []
    for p in data.get("previews") or []:
        previews.append(
            {
                "generated_voice_id": p.get("generated_voice_id"),
                "audio_base_64": p.get("audio_base_64"),
                "media_type": p.get("media_type") or "audio/mpeg",
                "duration_secs": p.get("duration_secs"),
                "language": p.get("language"),
            }
        )
    return {
        "voice_description": description,
        "model_id": body["model_id"],
        "text": data.get("text"),
        "previews": previews,
        "examples": EXAMPLE_DESCRIPTIONS,
        "iteration_note": (
            "Generate → preview → adjust description/seed → regenerate before saving. "
            "Saving creates an org-reusable custom voice."
        ),
    }


def create_voice_from_preview(
    settings: Settings,
    *,
    generated_voice_id: str,
    name: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Persist a designed voice via POST /v1/text-to-voice."""
    api_key = (settings.elevenlabs_api_key or "").strip()
    if not api_key:
        raise VoiceProviderError(
            "ElevenLabs TTS is not configured",
            status_code=503,
            error_class="not_configured",
            provider="elevenlabs",
        )
    gid = (generated_voice_id or "").strip()
    if not gid:
        raise VoiceProviderError(
            "generated_voice_id is required",
            status_code=400,
            error_class="validation",
        )
    body = {
        "voice_name": (name or "Custom voice").strip()[:100],
        "voice_description": (description or "Gravitre custom voice").strip()[:500],
        "generated_voice_id": gid,
    }
    url = "https://api.elevenlabs.io/v1/text-to-voice"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, json=body)
    if resp.status_code >= 400:
        _raise_upstream("ElevenLabs", resp)
    data = resp.json()
    voice_id = str(data.get("voice_id") or data.get("voiceId") or "")
    return {
        "voice_id": voice_id,
        "name": body["voice_name"],
        "description": body["voice_description"],
        "source": "custom_voice_v3",
        "reusable_across_org_agents": True,
        "reuse_note": (
            "Saved Custom Voices are org-scoped and reusable across other agents in the "
            "same organization (stored in agent_custom_voices + ElevenLabs account)."
        ),
        "raw": data,
    }


def design_examples() -> list[dict[str, Any]]:
    return list(EXAMPLE_DESCRIPTIONS)
