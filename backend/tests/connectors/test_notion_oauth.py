from __future__ import annotations

from types import SimpleNamespace

from app.connectors.notion_oauth import (
    normalize_vendor,
    notion_authorize_url,
    notion_oauth_configured,
    notion_redirect_uri,
)


def test_normalize_vendor_notion():
    assert normalize_vendor("Notion") == "notion"


def test_notion_oauth_configured():
    settings = SimpleNamespace(notion_client_id="cid", notion_client_secret="sec")
    assert notion_oauth_configured(settings) is True


def test_notion_redirect_and_authorize_url():
    settings = SimpleNamespace(api_public_url="https://api.example.com", public_app_url="")
    redirect = notion_redirect_uri(settings)
    assert redirect.endswith("/api/connectors/oauth/notion/callback")
    url = notion_authorize_url("cid", redirect, "state123")
    assert "client_id=cid" in url
    assert "owner=user" in url
