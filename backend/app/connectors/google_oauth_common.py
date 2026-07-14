"""Shared Google OAuth2 client credentials (Gravitre OAuth app)."""
from __future__ import annotations

from app.config import Settings
from app.public_urls import connector_oauth_callback_url

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Single redirect path for ALL Google connector products (GA4, Gmail, Drive, GSC, …).
# Product identity lives in signed OAuth state (`provider`), not in the callback URL.
# GCP Console only needs this one connector redirect URI (plus Supabase login callback).
GOOGLE_OAUTH_SHARED_CALLBACK_VENDOR = "google"


def google_oauth_credentials(settings: Settings, environment_name: str | None = None) -> tuple[str, str]:
    """Prefer GOOGLE_OAUTH_*; fall back to GOOGLE_ANALYTICS_* for backward compatibility."""
    _ = environment_name
    client_id = (
        (getattr(settings, "google_oauth_client_id", None) or getattr(settings, "google_analytics_client_id", None) or "")
        .strip()
    )
    client_secret = (
        (
            getattr(settings, "google_oauth_client_secret", None)
            or getattr(settings, "google_analytics_client_secret", None)
            or ""
        ).strip()
    )
    return client_id, client_secret


def google_oauth_configured(settings: Settings, environment_name: str | None = None) -> bool:
    client_id, client_secret = google_oauth_credentials(settings, environment_name)
    return bool(client_id and client_secret)


def google_oauth_redirect_uri(settings: Settings, provider: str | None = None) -> str:
    """Shared redirect URI for every Google connector product.

    ``provider`` is accepted for call-site compatibility but ignored — all Google
    products use ``/api/connectors/oauth/google/callback``.
    """
    _ = provider
    return connector_oauth_callback_url(
        public_app_url=settings.public_app_url,
        api_public_url=settings.api_public_url,
        vendor=GOOGLE_OAUTH_SHARED_CALLBACK_VENDOR,
    )
