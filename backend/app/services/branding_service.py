"""White-label branding stored in org settings (STA-84)."""
from __future__ import annotations

import secrets
from typing import Any

DEFAULT_BRANDING = {
    "logoUrl": None,
    "primaryColor": "#0f172a",
    "customDomain": None,
    "customDomainVerified": False,
    "customDomainVerifiedAt": None,
    "domainVerificationToken": None,
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
    previous_domain = branding.get("customDomain")
    for key, value in updates.items():
        if key in DEFAULT_BRANDING:
            branding[key] = value
    if "customDomain" in updates and updates.get("customDomain") != previous_domain:
        branding["customDomainVerified"] = False
        branding["customDomainVerifiedAt"] = None
        branding["domainVerificationToken"] = secrets.token_urlsafe(24)
    enterprise["branding"] = branding
    settings["enterprise"] = enterprise
    return settings


def ensure_domain_verification_token(org_settings: dict[str, Any] | None) -> dict[str, Any]:
    settings = dict(org_settings or {})
    enterprise = dict(settings.get("enterprise") or {})
    branding = dict(enterprise.get("branding") or DEFAULT_BRANDING)
    if branding.get("customDomain") and not branding.get("domainVerificationToken"):
        branding["domainVerificationToken"] = secrets.token_urlsafe(24)
    enterprise["branding"] = branding
    settings["enterprise"] = enterprise
    return settings


def mark_domain_verified(org_settings: dict[str, Any] | None, *, verified_at: str) -> dict[str, Any]:
    settings = dict(org_settings or {})
    enterprise = dict(settings.get("enterprise") or {})
    branding = dict(enterprise.get("branding") or DEFAULT_BRANDING)
    branding["customDomainVerified"] = True
    branding["customDomainVerifiedAt"] = verified_at
    enterprise["branding"] = branding
    settings["enterprise"] = enterprise
    return settings
