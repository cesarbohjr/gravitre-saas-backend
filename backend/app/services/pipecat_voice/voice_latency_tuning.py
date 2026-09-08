"""Voice 3.0 Phase 4 — latency tuning presets (speculative + TTS chunk + A/B eval)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Eval-only TTS models — never the live default; require VOICE_TTS_AB_V1=true.
TTS_AB_EVAL_MODELS: frozenset[str] = frozenset(
    {
        "eleven_v3",
        "eleven_turbo_v2_5",
        "eleven_multilingual_v2",
    }
)


@dataclass(frozen=True)
class VoiceSpeculativeTuning:
    v2_enabled: bool
    min_chars: int
    prefix_adopt: bool
    prefix_max_extra_words: int


@dataclass(frozen=True)
class VoiceTtsChunkTuning:
    v2_enabled: bool
    min_chars: int


@dataclass(frozen=True)
class VoiceTtsAbEval:
    enabled: bool
    model: str | None


def resolve_voice_speculative_tuning(settings: Any) -> VoiceSpeculativeTuning:
    v2 = bool(getattr(settings, "voice_speculative_v2", False))
    raw_min = int(getattr(settings, "voice_speculative_min_chars", 8) or 8)
    min_chars = max(4, min(raw_min, 32)) if v2 else 8
    prefix_adopt = v2 and bool(getattr(settings, "voice_speculative_prefix_adopt", True))
    extra_words = max(0, min(int(getattr(settings, "voice_speculative_prefix_max_words", 3) or 3), 8))
    return VoiceSpeculativeTuning(
        v2_enabled=v2,
        min_chars=min_chars,
        prefix_adopt=prefix_adopt,
        prefix_max_extra_words=extra_words,
    )


def resolve_voice_tts_chunk_tuning(settings: Any) -> VoiceTtsChunkTuning:
    v2 = bool(getattr(settings, "voice_tts_chunk_v2", False))
    raw_min = int(getattr(settings, "voice_tts_chunk_min_chars", 12) or 12)
    min_chars = max(6, min(raw_min, 24)) if v2 else 12
    if v2 and raw_min == 12:
        min_chars = 8
    return VoiceTtsChunkTuning(v2_enabled=v2, min_chars=min_chars)


def resolve_voice_tts_ab_eval(settings: Any) -> VoiceTtsAbEval:
    enabled = bool(getattr(settings, "voice_tts_ab_v1", False))
    model = (getattr(settings, "voice_tts_ab_model", None) or "").strip() or None
    if not enabled or not model:
        return VoiceTtsAbEval(enabled=False, model=None)
    normalized = model.strip().lower()
    if normalized not in TTS_AB_EVAL_MODELS:
        return VoiceTtsAbEval(enabled=False, model=None)
    return VoiceTtsAbEval(enabled=True, model=normalized)


def speculative_interim_materially_changed(previous: str, new: str) -> bool:
    """True when new partial revises earlier words — not a simple suffix extension."""
    from app.services.pipecat_voice.speculative_generation import _normalize_for_match

    prev = _normalize_for_match(previous)
    curr = _normalize_for_match(new)
    if not prev or not curr:
        return prev != curr
    if curr == prev:
        return False
    if curr.startswith(prev):
        return False
    return True
