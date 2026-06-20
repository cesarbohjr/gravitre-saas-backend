"""Canonical public URLs for production (custom domains on Vercel / Railway)."""
from __future__ import annotations

PRODUCTION_APP_URL = "https://gravitre.app"
PRODUCTION_API_URL = "https://api.gravitre.app"

_LEGACY_PUBLIC_HOSTS = ("vercel.app", "railway.app", "up.railway.app")


def is_legacy_platform_host(url: str) -> bool:
    lowered = (url or "").strip().lower()
    return any(host in lowered for host in _LEGACY_PUBLIC_HOSTS)


def normalize_public_url(url: str, *, fallback: str) -> str:
    """Return a user-facing URL, replacing platform default hosts with custom domains."""
    cleaned = (url or "").strip().rstrip("/")
    if not cleaned or is_legacy_platform_host(cleaned):
        return fallback.rstrip("/")
    return cleaned
