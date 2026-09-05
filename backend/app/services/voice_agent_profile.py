"""Per-agent voice profile + self-recognition prompt injection (Module D pattern)."""
from __future__ import annotations

from typing import Any

VALID_TTS_MODELS = {
    "eleven_flash_v2_5",
    "eleven_turbo_v2_5",
    "eleven_multilingual_v2",
    "eleven_v3",
    "eleven_multilingual_v2",
}

VALID_VOICE_SOURCES = {"preset_library", "custom_voice_v3"}


def normalize_voice_profile(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {
            "voice_source": None,
            "voice_id": None,
            "voice_key": None,
            "tts_model": "eleven_flash_v2_5",
            "personality_attributes": {},
            "turn_sensitivity": "normal",
        }
    source = raw.get("voice_source") or raw.get("source")
    if source and source not in VALID_VOICE_SOURCES:
        source = "preset_library"
    model = str(raw.get("tts_model") or raw.get("model") or "eleven_flash_v2_5").strip()
    if model == "eleven_turbo_v2_5":
        model = "eleven_flash_v2_5"
    if model not in VALID_TTS_MODELS:
        model = "eleven_flash_v2_5"
    personality = raw.get("personality_attributes") or raw.get("personality") or {}
    if not isinstance(personality, dict):
        personality = {}
    return {
        "voice_source": source,
        "voice_id": (str(raw.get("voice_id") or "").strip() or None),
        "voice_key": (str(raw.get("voice_key") or "").strip() or None),
        "tts_model": model,
        "personality_attributes": {
            "descriptor": str(personality.get("descriptor") or ""),
            "tone": str(personality.get("tone") or ""),
            "energy": str(personality.get("energy") or ""),
            "formality": str(personality.get("formality") or ""),
            "archetype": str(personality.get("archetype") or ""),
        },
        "turn_sensitivity": str(raw.get("turn_sensitivity") or "normal").lower(),
        "language": str(raw.get("language") or "en").lower()[:8],
    }


def agent_self_recognition_section(agent: dict[str, Any]) -> str:
    """Inject assigned name into system context (Module D-style section, not a fork)."""
    name = str(agent.get("name") or "").strip()
    if not name:
        return ""
    profile = normalize_voice_profile(agent.get("voice_profile") or agent.get("voiceProfile"))
    pers = profile.get("personality_attributes") or {}
    bits = []
    if pers.get("tone"):
        bits.append(f"tone={pers['tone']}")
    if pers.get("energy"):
        bits.append(f"energy={pers['energy']}")
    if pers.get("formality"):
        bits.append(f"formality={pers['formality']}")
    trait_line = f" Declared voice personality: {', '.join(bits)}." if bits else ""
    return f"""
## Agent self-recognition (assigned name)

Your assigned name is **{name}**. You know this name as a first-class identity fact.
When asked "what's your name" / "who are you", answer with {name} naturally.
When the user addresses you as "{name}" at the start of a turn (e.g. "Hey {name}…"),
respond as yourself — do not pretend to be unnamed or generic.
{trait_line}
""".strip()


def spoken_register_section() -> str:
    """Voice-turn spoken register — extends Module D registers, does not replace them."""
    return """
## Register 5 — SPOKEN (voice turns only)

When this turn will be spoken aloud (voice mode), use the SPOKEN register on top of
the dominant CONVERSATIONAL / OPERATIONAL / BLOCKED / CORRECTION register:

- Default to 1–3 short sentences per turn. Only go longer when the user's own
  message was long, or the facts genuinely require more (e.g. reading back a
  multi-field confirmation) — never pad a short answer to sound thorough.
- Lead with the single most important fact or answer, first sentence, before any
  supporting detail, caveat, or context. The user should get the answer even if
  they only hear the first sentence.
- Never restate or paraphrase the user's question back to them before answering
  ("So you're asking whether…", "Great question about…"). Answer directly.
- No unnecessary filler or preamble: no "Certainly!", "Great question!", "Sure
  thing!", "There are several possible reasons for that…", "I'd be happy to help
  with that." Start with the substance.
- Prefer shorter sentences throughout. Aim for natural spoken rhythm.
- Never use markdown headers, bullet lists, numbered lists, tables, or code fences.
- Prefer spoken transitions: "first… then… finally…" instead of "1. 2. 3."
- Avoid dense, list-heavy, visually formatted output that reads fine on screen but
  sounds unnatural or confusing when heard.
- Keep write-approval asks clear in speech: "Reply yes to confirm, or cancel to drop it."
- Do not spell out URLs character-by-character unless the user asks.
""".strip()
