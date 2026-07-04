"""Load domain taxonomy and intelligence profiles from YAML."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_DOMAIN_ROOT = Path(__file__).resolve().parent
_TAXONOMY_PATH = _DOMAIN_ROOT / "taxonomy.yaml"
_PROFILES_DIR = _DOMAIN_ROOT / "profiles"


@lru_cache(maxsize=1)
def load_taxonomy() -> dict[str, Any]:
    with _TAXONOMY_PATH.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=32)
def load_domain_profile(profile_id: str) -> dict[str, Any] | None:
    normalized = str(profile_id or "").strip().lower().replace(" ", "_")
    if not normalized:
        return None
    path = _PROFILES_DIR / f"{normalized}.yaml"
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else None


def list_profile_ids() -> list[str]:
    return sorted(path.stem for path in _PROFILES_DIR.glob("*.yaml"))


def resolve_industry_key(raw: str | None) -> str | None:
    if not raw:
        return None
    taxonomy = load_taxonomy()
    industries = taxonomy.get("industries") or {}
    lowered = str(raw).strip().lower()
    for key, meta in industries.items():
        if not isinstance(meta, dict):
            continue
        if lowered == key or lowered == str(meta.get("label") or "").lower():
            return key
        aliases = meta.get("aliases") or []
        if any(lowered == str(alias).lower() for alias in aliases):
            return key
        if any(str(alias).lower() in lowered for alias in aliases):
            return key
    return None


def resolve_department_key(raw: str | None) -> str | None:
    if not raw:
        return None
    taxonomy = load_taxonomy()
    departments = taxonomy.get("departments") or {}
    lowered = str(raw).strip().lower().replace(" ", "_")
    for key, meta in departments.items():
        if not isinstance(meta, dict):
            continue
        if lowered == key or lowered == str(meta.get("label") or "").lower().replace(" ", "_"):
            return key
    return lowered if lowered in departments else None
