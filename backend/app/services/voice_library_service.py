"""Curated preset voice library from ElevenLabs + structured personality metadata."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.services.tier1_voice_service import VoiceProviderError, _raise_upstream

# Structured personality metadata layered onto ElevenLabs shared voices.
# Keys match / can extend ElevenLabs voice_id when live API returns them.
CURATED_VOICE_META: dict[str, dict[str, Any]] = {
    "21m00Tcm4TlvDq8ikWAM": {  # Rachel
        "key": "rachel",
        "descriptor": "Clear, professional, composed",
        "tone": "professional",
        "energy": "steady",
        "formality": "formal",
        "gender": "female",
        "age_range": "young_adult",
        "accent_region": "american",
        "archetype": "operator",
        "categories": ["customer_success", "operations", "general"],
        "languages": ["en"],
        "models": ["eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_multilingual_v2", "eleven_v3"],
    },
    "pNInz6obpgDQGcFmaJgB": {  # Adam
        "key": "adam",
        "descriptor": "Clear professional male, measured",
        "tone": "professional",
        "energy": "calm",
        "formality": "formal",
        "gender": "male",
        "age_range": "adult",
        "accent_region": "american",
        "archetype": "advisor",
        "categories": ["sales", "finance", "general"],
        "languages": ["en"],
        "models": ["eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_multilingual_v2", "eleven_v3"],
    },
    "TxGEqnHWrfWFTfGW9XjX": {  # Josh
        "key": "josh",
        "descriptor": "Conversational, approachable male",
        "tone": "friendly",
        "energy": "warm",
        "formality": "casual",
        "gender": "male",
        "age_range": "young_adult",
        "accent_region": "american",
        "archetype": "teammate",
        "categories": ["support", "marketing", "general"],
        "languages": ["en"],
        "models": ["eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_multilingual_v2"],
    },
    "EXAVITQu4vr4xnSDxMaL": {  # Sarah
        "key": "sarah",
        "descriptor": "Soft, reassuring, customer-facing",
        "tone": "warm",
        "energy": "gentle",
        "formality": "neutral",
        "gender": "female",
        "age_range": "adult",
        "accent_region": "american",
        "archetype": "support",
        "categories": ["support", "hr", "customer_success"],
        "languages": ["en"],
        "models": ["eleven_flash_v2_5", "eleven_multilingual_v2", "eleven_v3"],
    },
    "VR6AewLTigWG4xSOukaG": {  # Arnold
        "key": "arnold",
        "descriptor": "Deep, authoritative, steady",
        "tone": "authoritative",
        "energy": "low",
        "formality": "formal",
        "gender": "male",
        "age_range": "mature",
        "accent_region": "american",
        "archetype": "executive",
        "categories": ["finance", "operations", "executive"],
        "languages": ["en"],
        "models": ["eleven_flash_v2_5", "eleven_multilingual_v2"],
    },
    "ThT5KcBeYPX3keUQqHPh": {  # Dorothy
        "key": "dorothy",
        "descriptor": "Pleasant, articulate British",
        "tone": "polished",
        "energy": "steady",
        "formality": "formal",
        "gender": "female",
        "age_range": "adult",
        "accent_region": "british",
        "archetype": "advisor",
        "categories": ["general", "operations", "executive"],
        "languages": ["en"],
        "models": ["eleven_flash_v2_5", "eleven_multilingual_v2", "eleven_v3"],
    },
    "pqHfZKP75CvOlQylNhV4": {  # Bill
        "key": "bill",
        "descriptor": "Mature, trustworthy narrator",
        "tone": "trustworthy",
        "energy": "calm",
        "formality": "neutral",
        "gender": "male",
        "age_range": "mature",
        "accent_region": "american",
        "archetype": "narrator",
        "categories": ["general", "finance"],
        "languages": ["en"],
        "models": ["eleven_flash_v2_5", "eleven_multilingual_v2"],
    },
    "XrExE9yKIg1WjnnlVkGX": {  # Matilda
        "key": "matilda",
        "descriptor": "Bright, energetic, marketing-forward",
        "tone": "upbeat",
        "energy": "high",
        "formality": "casual",
        "gender": "female",
        "age_range": "young_adult",
        "accent_region": "american",
        "archetype": "marketer",
        "categories": ["marketing", "sales"],
        "languages": ["en"],
        "models": ["eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_v3"],
    },
    "JBFqnCBsd6RMkjVDRZzb": {  # George
        "key": "george",
        "descriptor": "Warm British male, composed",
        "tone": "warm",
        "energy": "steady",
        "formality": "neutral",
        "gender": "male",
        "age_range": "adult",
        "accent_region": "british",
        "archetype": "teammate",
        "categories": ["support", "general", "hr"],
        "languages": ["en"],
        "models": ["eleven_flash_v2_5", "eleven_multilingual_v2"],
    },
    "onwK4e9ZLuTAKqWW03F9": {  # Daniel
        "key": "daniel",
        "descriptor": "Crisp British newsreader",
        "tone": "crisp",
        "energy": "measured",
        "formality": "formal",
        "gender": "male",
        "age_range": "adult",
        "accent_region": "british",
        "archetype": "analyst",
        "categories": ["operations", "finance", "executive"],
        "languages": ["en"],
        "models": ["eleven_flash_v2_5", "eleven_multilingual_v2", "eleven_v3"],
    },
    "cgSgspJ2msm6clMCkdW9": {  # Jessica
        "key": "jessica",
        "descriptor": "Expressive American, lively",
        "tone": "expressive",
        "energy": "high",
        "formality": "casual",
        "gender": "female",
        "age_range": "young_adult",
        "accent_region": "american",
        "archetype": "marketer",
        "categories": ["marketing", "sales", "support"],
        "languages": ["en"],
        "models": ["eleven_flash_v2_5", "eleven_v3"],
    },
    "cjVigY5qzO86Huf0OWal": {  # Eric
        "key": "eric",
        "descriptor": "Friendly midwestern American",
        "tone": "friendly",
        "energy": "warm",
        "formality": "casual",
        "gender": "male",
        "age_range": "adult",
        "accent_region": "american",
        "archetype": "teammate",
        "categories": ["support", "hr", "general"],
        "languages": ["en"],
        "models": ["eleven_flash_v2_5", "eleven_multilingual_v2"],
    },
}

CATEGORY_LABELS = {
    "general": "General",
    "customer_success": "Customer success",
    "operations": "Operations",
    "sales": "Sales",
    "finance": "Finance",
    "support": "Support",
    "marketing": "Marketing",
    "hr": "HR",
    "executive": "Executive",
}


def _fallback_library() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for voice_id, meta in CURATED_VOICE_META.items():
        out.append(
            {
                "voice_id": voice_id,
                "key": meta["key"],
                "name": meta["key"].title(),
                "source": "preset_library",
                "preview_url": None,
                "language_flag": "en" if "en" in meta["languages"] else meta["languages"][0],
                "languages": list(meta["languages"]),
                "models": list(meta["models"]),
                "personality": {
                    "descriptor": meta["descriptor"],
                    "tone": meta["tone"],
                    "energy": meta["energy"],
                    "formality": meta["formality"],
                    "gender": meta["gender"],
                    "age_range": meta["age_range"],
                    "accent_region": meta["accent_region"],
                    "archetype": meta["archetype"],
                },
                "categories": list(meta["categories"]),
            }
        )
    return out


def fetch_elevenlabs_shared_voices(settings: Settings) -> list[dict[str, Any]]:
    """Pull live voices from ElevenLabs; enrich with curated metadata."""
    api_key = (settings.elevenlabs_api_key or "").strip()
    curated = _fallback_library()
    by_id = {v["voice_id"]: v for v in curated}
    if not api_key:
        return curated
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": api_key}
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, headers=headers)
        if resp.status_code >= 400:
            _raise_upstream("ElevenLabs", resp)
        data = resp.json()
    except VoiceProviderError:
        return curated
    except Exception:  # noqa: BLE001
        return curated

    for raw in data.get("voices") or []:
        vid = str(raw.get("voice_id") or "")
        if not vid:
            continue
        labels = raw.get("labels") or {}
        base = by_id.get(vid)
        if base:
            base["name"] = str(raw.get("name") or base["name"])
            base["preview_url"] = raw.get("preview_url")
            if labels.get("language"):
                lang = str(labels["language"]).lower()[:8]
                if lang not in base["languages"]:
                    base["languages"].append(lang)
            continue
        # Include additional ElevenLabs voices with inferred metadata
        gender = str(labels.get("gender") or "unspecified").lower()
        accent = str(labels.get("accent") or labels.get("language") or "unspecified").lower()
        age = str(labels.get("age") or "adult").lower()
        descriptive = str(labels.get("description") or labels.get("use case") or "Shared library voice")
        entry = {
            "voice_id": vid,
            "key": vid,
            "name": str(raw.get("name") or vid[:8]),
            "source": "preset_library",
            "preview_url": raw.get("preview_url"),
            "language_flag": str(labels.get("language") or "en")[:8],
            "languages": [str(labels.get("language") or "en")[:8]],
            "models": ["eleven_flash_v2_5", "eleven_multilingual_v2"],
            "personality": {
                "descriptor": descriptive,
                "tone": str(labels.get("descriptive") or "neutral"),
                "energy": "steady",
                "formality": "neutral",
                "gender": gender,
                "age_range": age,
                "accent_region": accent,
                "archetype": "general",
            },
            "categories": ["general"],
        }
        by_id[vid] = entry
        curated.append(entry)
    return curated


def list_voice_library(
    settings: Settings,
    *,
    category: str | None = None,
    language: str | None = None,
    gender: str | None = None,
    archetype: str | None = None,
) -> dict[str, Any]:
    voices = fetch_elevenlabs_shared_voices(settings)
    cat = (category or "").strip().lower() or None
    lang = (language or "").strip().lower() or None
    gen = (gender or "").strip().lower() or None
    arch = (archetype or "").strip().lower() or None
    filtered: list[dict[str, Any]] = []
    for v in voices:
        if cat and cat not in (v.get("categories") or []):
            continue
        if lang and lang not in [x.lower() for x in (v.get("languages") or [])]:
            continue
        pers = v.get("personality") or {}
        if gen and str(pers.get("gender") or "").lower() != gen:
            continue
        if arch and str(pers.get("archetype") or "").lower() != arch:
            continue
        filtered.append(v)
    categories = sorted({c for v in voices for c in (v.get("categories") or [])})
    return {
        "voices": filtered,
        "count": len(filtered),
        "total_unfiltered": len(voices),
        "categories": [{"id": c, "label": CATEGORY_LABELS.get(c, c.title())} for c in categories],
        "filters_applied": {
            "category": cat,
            "language": lang,
            "gender": gen,
            "archetype": arch,
        },
        "language_note": (
            "Voices without the requested language are filtered out. Multilingual models "
            "(eleven_multilingual_v2 / eleven_v3) are flagged per voice under models[]."
        ),
    }


def recommend_voices_for_agent(
    settings: Settings,
    *,
    department: str | None = None,
    personality_traits: dict[str, Any] | None = None,
    model: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Correlate library voices with agent department / personality; admin may override."""
    lib = list_voice_library(settings)["voices"]
    dept = (department or "operations").strip().lower()
    dept_map = {
        "marketing": "marketing",
        "sales": "sales",
        "finance": "finance",
        "support": "support",
        "hr": "hr",
        "operations": "operations",
        "customer success": "customer_success",
    }
    cat = dept_map.get(dept, "general")
    traits = personality_traits or {}
    want_formality = str(traits.get("formality") or "").lower()
    want_energy = str(traits.get("energy") or "").lower()
    scored: list[tuple[int, dict[str, Any]]] = []
    for v in lib:
        score = 0
        if cat in (v.get("categories") or []):
            score += 3
        if "general" in (v.get("categories") or []):
            score += 1
        pers = v.get("personality") or {}
        if want_formality and want_formality == str(pers.get("formality") or "").lower():
            score += 2
        if want_energy and want_energy == str(pers.get("energy") or "").lower():
            score += 2
        if model and model in (v.get("models") or []):
            score += 1
        scored.append((score, v))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("name") or "")))
    out = []
    for score, v in scored[: max(1, limit)]:
        item = dict(v)
        item["recommendation_score"] = score
        item["recommendation_note"] = (
            "Correlated with department/personality; admin can always override."
        )
        out.append(item)
    return out
