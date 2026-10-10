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


def resolve_voice_speculative_bounds(settings: Any) -> Any:
    """Per-run speculation limits (always on; Settings may tighten or loosen
    within hard clamps)."""
    from app.services.pipecat_voice.speculative_generation import SpeculativeBounds

    def _num(name: str, default: float) -> float:
        try:
            raw = getattr(settings, name, default)
            return float(default if raw is None else raw)
        except (TypeError, ValueError):
            return float(default)

    return SpeculativeBounds(
        timeout_s=max(0.5, min(_num("voice_speculative_timeout_s", 5.0), 20.0)),
        max_buffered_chars=int(max(200, min(_num("voice_speculative_max_buffer_chars", 2000), 20000))),
        max_buffered_events=int(max(32, min(_num("voice_speculative_max_buffer_events", 512), 4096))),
    )


def voice_request_revisions_enabled(settings: Any) -> bool:
    """Versioned request revisions + strict adoption: always on.

    Was voice_request_revisions_v1 (default off). A speculative answer is only
    safe to adopt under the strict contract, so it no longer depends on a
    setting; the variable is ignored.
    """
    del settings
    return True


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


def speculative_interim_breaks_run(
    run_text: str,
    new: str,
    *,
    strict: bool,
    v2_enabled: bool,
    max_extra_words: int,
) -> bool:
    """Should a new interim transcript cancel the pending speculative run?

    v1: any change. v2: any change that is not a pure suffix extension.
    Strict (voice_request_revisions_v1): any change that the strict adoption
    check would reject anyway ("...last month" -> "...last month but"), so the
    compute is freed at once instead of at confirmed end of turn.
    """
    if not v2_enabled and not strict:
        return True
    if strict:
        from app.services.pipecat_voice.speculative_generation import strict_transcript_match

        ok, _why = strict_transcript_match(
            run_text, new, max_extra_words=max_extra_words if v2_enabled else 0
        )
        return not ok
    return speculative_interim_materially_changed(run_text, new)
