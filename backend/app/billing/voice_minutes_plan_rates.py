"""Voice Minutes allotments and overage — mirrors research_lookup_plan_rates.

COGS basis (public list prices, Aug 2026 — flag for review):
  Deepgram Nova streaming (PAYG): ~$0.0077 / minute
  ElevenLabs Flash TTS: $0.05 / 1k chars ≈ $0.0375 / minute of continuous speech
  Duplex session minute (STT full + ~50% agent speech):
    $0.0077 + ($0.0375 * 0.5) = $0.02645 blended COGS

Gravitre uses ElevenAPI Flash + Deepgram (NOT ElevenAgents hosting at $0.08/min).
Proposed overage: $0.12 / minute ≈ 4.5× actual blended COGS (tunable without re-arch).
If pricing had used ElevenAgents $0.08 + Deepgram $0.0077 = $0.0877 × 3.5 ≈ $0.31.
"""
from __future__ import annotations

from typing import Any

# Flagged for review — mechanism ships; numbers tunable.
_FALLBACK_INCLUDED: dict[str, int] = {
    "node": 60,
    "control": 300,
    "command": 1200,
    "enterprise": 1200,
    "free": 0,
    "starter": 60,
    "growth": 300,
    "scale": 1200,
}
_FALLBACK_OVERAGE_USD = 0.12

COGS_DEEPGRAM_STREAMING_USD_PER_MIN = 0.0077
COGS_ELEVENLABS_FLASH_USD_PER_MIN_CONTINUOUS = 0.0375
COGS_BLENDED_DUPLEX_USD_PER_MIN = 0.02645
OVERAGE_MULTIPLIER_ON_BLENDED = round(_FALLBACK_OVERAGE_USD / COGS_BLENDED_DUPLEX_USD_PER_MIN, 2)


def cogs_report() -> dict[str, Any]:
    return {
        "architecture": "elevenapi_flash_tts + deepgram_streaming_stt",
        "not_using": "elevenagents_conversational_ai_hosting",
        "deepgram_streaming_usd_per_min": COGS_DEEPGRAM_STREAMING_USD_PER_MIN,
        "elevenlabs_flash_usd_per_min_continuous_speech": COGS_ELEVENLABS_FLASH_USD_PER_MIN_CONTINUOUS,
        "blended_duplex_cogs_usd_per_min": COGS_BLENDED_DUPLEX_USD_PER_MIN,
        "math": "0.0077 + (0.0375 * 0.5) = 0.02645",
        "proposed_overage_usd_per_min": _FALLBACK_OVERAGE_USD,
        "multiplier_on_blended_cogs": OVERAGE_MULTIPLIER_ON_BLENDED,
        "elevenagents_reference_usd_per_min": 0.08,
        "if_priced_on_elevenagents_plus_deepgram": {
            "cogs": 0.0877,
            "at_3_5x": 0.307,
        },
        "sources": [
            "https://deepgram.com/pricing",
            "https://elevenlabs.io/pricing/api",
            "https://elevenlabs.io/pricing/agents",
        ],
        "flag_for_review": True,
    }


def _plan_code(plan: dict[str, Any] | None, plan_code: str | None = None) -> str:
    if plan_code:
        return str(plan_code).strip().lower()
    if plan:
        return str(plan.get("code") or "node").strip().lower()
    return "node"


def included_voice_minutes_for_plan(
    plan: dict[str, Any] | None,
    *,
    plan_code: str | None = None,
) -> int:
    code = _plan_code(plan, plan_code)
    if plan:
        features = plan.get("features") if isinstance(plan.get("features"), dict) else {}
        raw = features.get("voice_minutes_per_month")
        if raw is not None:
            try:
                return max(int(raw), 0)
            except (TypeError, ValueError):
                pass
    return int(_FALLBACK_INCLUDED.get(code, _FALLBACK_INCLUDED["node"]))


def overage_usd_per_voice_minute(plan: dict[str, Any] | None) -> float:
    if plan:
        rates = plan.get("overage_rates") if isinstance(plan.get("overage_rates"), dict) else {}
        raw = rates.get("voice_minute")
        if raw is not None:
            try:
                return max(float(raw), 0.0)
            except (TypeError, ValueError):
                pass
    return _FALLBACK_OVERAGE_USD
