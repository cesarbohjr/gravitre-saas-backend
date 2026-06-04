from __future__ import annotations

from types import SimpleNamespace

from app.connectors.jira_oauth import (
    jira_authorize_url,
    jira_oauth_configured,
    jira_redirect_uri,
    normalize_vendor,
    pick_jira_cloud_site,
)


def test_normalize_vendor_jira():
    assert normalize_vendor("Jira") == "jira"
    assert normalize_vendor("jira-cloud") == "jira"


def test_jira_oauth_configured():
    settings = SimpleNamespace(jira_client_id="cid", jira_client_secret="sec")
    assert jira_oauth_configured(settings) is True


def test_jira_redirect_and_authorize_url():
    settings = SimpleNamespace(api_public_url="https://api.example.com", public_app_url="")
    redirect = jira_redirect_uri(settings)
    assert redirect.endswith("/api/connectors/oauth/jira/callback")
    url = jira_authorize_url("cid", redirect, "state123")
    assert "auth.atlassian.com" in url
    assert "write%3Ajira-work" in url or "write:jira-work" in url


def test_pick_jira_cloud_site_prefers_jira_scope():
    sites = [
        {"id": "a", "scopes": ["read:confluence"]},
        {"id": "b", "scopes": ["read:jira-work", "write:jira-work"]},
    ]
    picked = pick_jira_cloud_site(sites)
    assert picked is not None
    assert picked["id"] == "b"
