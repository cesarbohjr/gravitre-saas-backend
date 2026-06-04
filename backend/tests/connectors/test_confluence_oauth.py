from __future__ import annotations

from types import SimpleNamespace

from app.connectors.confluence_oauth import (
    confluence_authorize_url,
    confluence_credentials,
    confluence_oauth_configured,
    confluence_redirect_uri,
    normalize_vendor,
    pick_confluence_cloud_site,
)


def test_normalize_vendor_confluence():
    assert normalize_vendor("Confluence") == "confluence"
    assert normalize_vendor("confluence-cloud") == "confluence"


def test_confluence_oauth_configured_uses_jira_credentials_fallback():
    settings = SimpleNamespace(
        confluence_client_id="",
        confluence_client_secret="",
        jira_client_id="cid",
        jira_client_secret="sec",
    )
    assert confluence_credentials(settings) == ("cid", "sec")
    assert confluence_oauth_configured(settings) is True


def test_confluence_redirect_and_authorize_url():
    settings = SimpleNamespace(api_public_url="https://api.example.com", public_app_url="")
    redirect = confluence_redirect_uri(settings)
    assert redirect.endswith("/api/connectors/oauth/confluence/callback")
    url = confluence_authorize_url("cid", redirect, "state123")
    assert "auth.atlassian.com" in url
    assert "confluence" in url.lower()


def test_pick_confluence_cloud_site_prefers_confluence_scope():
    sites = [
        {"id": "a", "scopes": ["read:jira-work"]},
        {"id": "b", "scopes": ["read:confluence-content.all"]},
    ]
    picked = pick_confluence_cloud_site(sites)
    assert picked is not None
    assert picked["id"] == "b"
