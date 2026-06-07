"""White-label branding stored in org settings (STA-84)."""
from __future__ import annotations

from typing import Any

DEFAULT_BRANDING = {
    "logoUrl": None,
    "primaryColor": "#0f172a",
    "customDomain": None,
    "hidePoweredBy": False,
    "emailFromName": "Gravitre",
}


def get_org_branding(org_settings: dict[str, Any] | None) -> dict[str, Any]:
    settings = org_settings or {}
    enterprise = settings.get("enterprise") if isinstance(settings.get("enterprise"), dict) else {}
    branding = enterprise.get("branding") if isinstance(enterprise.get("branding"), dict) else {}
    merged = dict(DEFAULT_BRANDING)
    merged.update({k: v for k, v in branding.items() if k in DEFAULT_BRANDING})
    return merged


def merge_branding(org_settings: dict[str, Any] | None, updates: dict[str, Any]) -> dict[str, Any]:
    settings = dict(org_settings or {})
    enterprise = dict(settings.get("enterprise") or {})
    branding = dict(enterprise.get("branding") or DEFAULT_BRANDING)
    for key, value in updates.items():
        if key in DEFAULT_BRANDING:
            branding[key] = value
    enterprise["branding"] = branding
    settings["enterprise"] = enterprise
    return settings
