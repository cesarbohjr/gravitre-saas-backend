from app.config import Settings
from app.connectors.generic_oauth import generic_redirect_uri
from app.public_urls import (
    PRODUCTION_APP_URL,
    PRODUCTION_API_URL,
    connector_oauth_callback_url,
    is_legacy_platform_host,
    normalize_public_url,
)


def test_is_legacy_platform_host():
    assert is_legacy_platform_host("https://gravitre-saas-backend-production.up.railway.app")
    assert is_legacy_platform_host("https://web-foo-gravitre-ai.vercel.app")
    assert not is_legacy_platform_host("https://api.gravitre.app")


def test_normalize_public_url_replaces_legacy_hosts():
    assert (
        normalize_public_url(
            "https://gravitre-saas-backend-production.up.railway.app",
            fallback=PRODUCTION_API_URL,
        )
        == PRODUCTION_API_URL
    )
    assert normalize_public_url("", fallback=PRODUCTION_APP_URL) == PRODUCTION_APP_URL
    assert (
        normalize_public_url("https://api.gravitre.app", fallback=PRODUCTION_API_URL)
        == "https://api.gravitre.app"
    )


def test_connector_oauth_callback_prefers_app_domain():
    uri = connector_oauth_callback_url(
        public_app_url="https://gravitre.app",
        api_public_url="https://api.gravitre.app",
        vendor="hubspot",
    )
    assert uri == "https://gravitre.app/api/connectors/oauth/hubspot/callback"


def test_settings_normalize_public_urls_in_production():
    settings = Settings(
        app_env="production",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        supabase_jwt_secret="jwt",
        openai_api_key="sk-test",
        connector_secrets_encryption_key="a" * 64,
        api_public_url="https://gravitre-saas-backend-production.up.railway.app",
        public_app_url="https://foo.vercel.app",
    )
    assert settings.api_public_url == ""
    assert settings.public_app_url == PRODUCTION_APP_URL


def test_generic_redirect_uri_uses_public_app_url():
    settings = Settings(
        supabase_url="https://x.supabase.co",
        supabase_anon_key="a",
        supabase_service_role_key="b",
        supabase_jwt_secret="c",
        api_public_url="https://api.gravitre.app",
        public_app_url="https://gravitre.app",
        NEXT_PUBLIC_APP_URL="https://gravitre.app",
    )
    assert (
        generic_redirect_uri(settings, "mailchimp")
        == "https://gravitre.app/api/connectors/oauth/mailchimp/callback"
    )
