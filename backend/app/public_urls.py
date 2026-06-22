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


def connector_oauth_callback_url(
    *,
    public_app_url: str,
    api_public_url: str,
    vendor: str,
) -> str:
    """OAuth redirect URI shown to users — prefer app domain (/api rewrite) over direct API host."""
    path = f"/api/connectors/oauth/{vendor}/callback"
    app_base = (public_app_url or "").strip().rstrip("/")
    if app_base and not is_legacy_platform_host(app_base):
        return f"{app_base}{path}"
    api_base = (api_public_url or "").strip().rstrip("/")
    if api_base and not is_legacy_platform_host(api_base):
        return f"{api_base}{path}"
    return f"http://localhost:8000{path}"
