"""White-label branding stored in org settings (STA-84)."""
from __future__ import annotations

import secrets
from typing import Any
from app.core.safe_dict import safe_normalize_stored_dict

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
    enterprise = safe_normalize_stored_dict(settings, key="enterprise")
    branding = safe_normalize_stored_dict(enterprise, key='branding') or safe_normalize_stored_dict(DEFAULT_BRANDING)
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
    enterprise = safe_normalize_stored_dict(settings, key="enterprise")
    branding = safe_normalize_stored_dict(enterprise, key='branding') or safe_normalize_stored_dict(DEFAULT_BRANDING)
    if branding.get("customDomain") and not branding.get("domainVerificationToken"):
        branding["domainVerificationToken"] = secrets.token_urlsafe(24)
    enterprise["branding"] = branding
    settings["enterprise"] = enterprise
    return settings


def mark_domain_verified(org_settings: dict[str, Any] | None, *, verified_at: str) -> dict[str, Any]:
    settings = dict(org_settings or {})
    enterprise = safe_normalize_stored_dict(settings, key="enterprise")
    branding = safe_normalize_stored_dict(enterprise, key='branding') or safe_normalize_stored_dict(DEFAULT_BRANDING)
    branding["customDomainVerified"] = True
    branding["customDomainVerifiedAt"] = verified_at
    enterprise["branding"] = branding
    settings["enterprise"] = enterprise
    return settings
