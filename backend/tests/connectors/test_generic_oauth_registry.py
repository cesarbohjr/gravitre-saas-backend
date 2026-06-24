"""Generic OAuth provider registry tests."""
from __future__ import annotations

from app.connectors.generic_oauth import generic_redirect_uri
from app.connectors.oauth_provider_registry import (
    GENERIC_OAUTH_VENDORS,
    OAUTH_PROVIDER_REGISTRY,
    PKCE_OAUTH_VENDORS,
    normalize_generic_vendor,
)
from app.config import Settings

INVALID_GENERIC_OAUTH = frozenset(
    {
        "claude",
        "sendgrid",
        "twilio",
        "mixpanel",
        "semrush",
        "stackadapt",
        "plaid",
        "mongodb",
        "bamboohr",
        "adp",
        "motion",
        "n8n",
        "apollo",
        "absorb_lms",
        "snowflake",
        "odoo",
    }
)


def test_invalid_vendors_not_in_registry():
    for vendor in INVALID_GENERIC_OAUTH:
        assert vendor not in GENERIC_OAUTH_VENDORS


def test_pkce_providers():
    assert PKCE_OAUTH_VENDORS == frozenset({"airtable", "canva", "xero"})
    for vendor in PKCE_OAUTH_VENDORS:
        assert OAUTH_PROVIDER_REGISTRY[vendor].requires_pkce is True


def test_plaid_not_oauth_vendor():
    assert normalize_generic_vendor("plaid") is None


def test_registry_size():
    assert len(GENERIC_OAUTH_VENDORS) == len(OAUTH_PROVIDER_REGISTRY)


def test_partner_gated_vendors():
    from app.connectors.oauth_provider_registry import PARTNER_GATED_OAUTH_VENDORS

    assert PARTNER_GATED_OAUTH_VENDORS == frozenset({"zapier", "hootsuite", "gusto", "canva"})
    for vendor in PARTNER_GATED_OAUTH_VENDORS:
        assert OAUTH_PROVIDER_REGISTRY[vendor].partner_gated is True


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


def test_clickup_redirect_uri_uses_app_domain_only():
    settings = Settings(
        supabase_url="https://x.supabase.co",
        supabase_anon_key="a",
        supabase_service_role_key="b",
        supabase_jwt_secret="c",
        api_public_url="https://api.gravitre.app",
        public_app_url="https://gravitre.app",
        NEXT_PUBLIC_APP_URL="https://gravitre.app",
    )
    assert generic_redirect_uri(settings, "clickup") == "https://gravitre.app"
