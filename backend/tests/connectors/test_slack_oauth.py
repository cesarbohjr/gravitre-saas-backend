from __future__ import annotations

from types import SimpleNamespace

from app.connectors.slack_oauth import (
    normalize_vendor,
    slack_authorize_url,
    slack_oauth_configured,
    slack_redirect_uri,
)


def test_normalize_vendor_slack():
    assert normalize_vendor("Slack") == "slack"
    assert normalize_vendor("slack") == "slack"


def test_slack_oauth_configured():
    settings = SimpleNamespace(slack_client_id="cid", slack_client_secret="sec")
    assert slack_oauth_configured(settings) is True


def test_slack_redirect_and_authorize_url():
    settings = SimpleNamespace(api_public_url="https://api.example.com")
    redirect = slack_redirect_uri(settings)
    assert redirect.endswith("/api/connectors/oauth/slack/callback")
    url = slack_authorize_url("cid", redirect, "state123")
    assert "slack.com/oauth/v2/authorize" in url
    assert "chat%3Awrite" in url or "chat:write" in url
