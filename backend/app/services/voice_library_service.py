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


def curated_voice_ids() -> list[str]:
    return list(CURATED_VOICE_META.keys())


def _sharing_multiplier_fields(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract credit-multiplier / free-user flags from ElevenLabs voice payload."""
    sharing = raw.get("sharing") if isinstance(raw.get("sharing"), dict) else {}
    rate = sharing.get("rate")
    try:
        rate_f = float(rate) if rate is not None else None
    except (TypeError, ValueError):
        rate_f = None
    # Multiplier present when sharing.rate is set and not the standard 1.0.
    has_multiplier = bool(rate_f is not None and abs(rate_f - 1.0) > 1e-6)
    free_allowed = sharing.get("free_users_allowed")
    if free_allowed is None:
        free_allowed = raw.get("free_users_allowed")
    return {
        "category": raw.get("category"),
        "sharing_rate": rate_f,
        "has_credit_multiplier": has_multiplier,
        "free_users_allowed": free_allowed,
        "fiat_rate": sharing.get("fiat_rate"),
        "sharing_status": sharing.get("status"),
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
                "has_credit_multiplier": None,
                "sharing_rate": None,
                "free_users_allowed": None,
                "multiplier_status": "unknown_offline",
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
        mult = _sharing_multiplier_fields(raw if isinstance(raw, dict) else {})
        base = by_id.get(vid)
        if base:
            base["name"] = str(raw.get("name") or base["name"])
            base["preview_url"] = raw.get("preview_url")
            base.update(mult)
            base["multiplier_status"] = (
                "has_multiplier" if mult["has_credit_multiplier"] else "no_multiplier"
            )
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
            **mult,
            "multiplier_status": (
                "has_multiplier" if mult["has_credit_multiplier"] else "no_multiplier"
            ),
        }
        by_id[vid] = entry
        curated.append(entry)
    return curated


def audit_curated_voice_multipliers(settings: Settings) -> dict[str, Any]:
    """GET /v1/voices for every curated preset id; report credit-multiplier flags.

    Also fetches per-voice detail when the list payload omits a curated id.
    """
    api_key = (settings.elevenlabs_api_key or "").strip()
    if not api_key:
        raise VoiceProviderError(
            "ElevenLabs TTS is not configured",
            status_code=503,
            error_class="not_configured",
            provider="elevenlabs",
        )
    headers = {"xi-api-key": api_key}
    by_id: dict[str, dict[str, Any]] = {}
    with httpx.Client(timeout=45.0) as client:
        resp = client.get("https://api.elevenlabs.io/v1/voices", headers=headers)
        if resp.status_code >= 400:
            _raise_upstream("ElevenLabs", resp)
        for raw in (resp.json() or {}).get("voices") or []:
            vid = str(raw.get("voice_id") or "")
            if vid:
                by_id[vid] = raw if isinstance(raw, dict) else {}

        rows: list[dict[str, Any]] = []
        for voice_id, meta in CURATED_VOICE_META.items():
            raw = by_id.get(voice_id)
            if raw is None:
                detail = client.get(
                    f"https://api.elevenlabs.io/v1/voices/{voice_id}", headers=headers
                )
                if detail.status_code < 400:
                    raw = detail.json()
                    by_id[voice_id] = raw if isinstance(raw, dict) else {}
                else:
                    rows.append(
                        {
                            "voice_id": voice_id,
                            "key": meta["key"],
                            "name": meta["key"].title(),
                            "found": False,
                            "has_credit_multiplier": None,
                            "sharing_rate": None,
                            "free_users_allowed": None,
                            "category": None,
                            "detail_http": detail.status_code,
                            "is_default_shortcut": meta["key"] in {"rachel", "adam", "josh"},
                        }
                    )
                    continue
            mult = _sharing_multiplier_fields(raw)
            rows.append(
                {
                    "voice_id": voice_id,
                    "key": meta["key"],
                    "name": str(raw.get("name") or meta["key"].title()),
                    "found": True,
                    "is_default_shortcut": meta["key"] in {"rachel", "adam", "josh"},
                    "archetype": meta.get("archetype"),
                    **mult,
                }
            )

    with_mult = [r for r in rows if r.get("has_credit_multiplier") is True]
    without = [r for r in rows if r.get("has_credit_multiplier") is False]
    unknown = [r for r in rows if r.get("has_credit_multiplier") is None]
    # Failed TTS prove used rachel / 21m00Tcm4TlvDq8ikWAM
    rachel = next((r for r in rows if r.get("voice_id") == "21m00Tcm4TlvDq8ikWAM"), None)
    if with_mult:
        recommendation = {
            "tier": "creator_or_swap",
            "note": (
                "One or more curated preset voices carry a credit multiplier. "
                "Either upgrade to Creator (or higher) if keeping them, or swap those "
                "voices for non-multiplier equivalents before purchasing Starter."
            ),
            "multiplier_voice_ids": [r["voice_id"] for r in with_mult],
        }
    else:
        recommendation = {
            "tier": "starter",
            "note": (
                "None of the currently-wired preset voices carry a credit multiplier "
                "flag in GET /v1/voices. Starter ($6/mo) is sufficient for API access "
                "to these voices; confirm paid_plan_required clears after Starter "
                "upgrade (separate from multiplier)."
            ),
            "multiplier_voice_ids": [],
        }
    return {
        "source": "GET https://api.elevenlabs.io/v1/voices (+ /v1/voices/{id} fallback)",
        "failed_prove_voice_id": "21m00Tcm4TlvDq8ikWAM",
        "failed_prove_voice": rachel,
        "voices": rows,
        "counts": {
            "curated": len(rows),
            "with_multiplier": len(with_mult),
            "without_multiplier": len(without),
            "unknown": len(unknown),
        },
        "recommendation": recommendation,
    }


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
