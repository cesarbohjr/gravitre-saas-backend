"""No external Slack traffic: invalid credentials must not be rechecked every turn."""
from types import SimpleNamespace
from unittest.mock import patch

from app.connectors import slack_oauth


def test_invalid_slack_token_backoff_and_immediate_recheck_after_rotation(monkeypatch):
    # Isolate per-test in-memory state (never inspect or log real credentials).
    monkeypatch.setattr(slack_oauth, "_slack_invalid_auth_until", {})
    monkeypatch.setattr(slack_oauth, "slack_oauth_configured", lambda *_args: True)
    monkeypatch.setattr(slack_oauth, "_connector_environment", lambda *_args: "acceptance")
    monkeypatch.setattr(
        "app.connectors.managed_oauth.managed_oauth_row",
        lambda *_args, **_kwargs: None,
    )
    tokens = ["invalid-token-a"]
    monkeypatch.setattr(
        slack_oauth, "get_decrypted_secret",
        lambda *_args, **_kwargs: tokens[0],
    )
    calls = []

    class FakeHTTP:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, url, **_kwargs):
            calls.append(url)
            return SimpleNamespace(json=lambda: {"ok": False, "error": "invalid_auth"})

    monkeypatch.setattr(slack_oauth.httpx, "Client", FakeHTTP)
    settings = SimpleNamespace(slack_client_id="id", slack_client_secret="secret")

    for _ in range(4):
        assert slack_oauth.slack_connection_auth_status(
            object(), "org-a", "conn-a", settings,
            environment_name="acceptance",
        ) == "auth_expired"
    assert len(calls) == 1, "A known invalid token must not be retried on every turn"

    tokens[0] = "invalid-token-b"
    assert slack_oauth.slack_connection_auth_status(
        object(), "org-a", "conn-a", settings,
        environment_name="acceptance",
    ) == "auth_expired"
    assert len(calls) == 2, "Reconnect/rotation must retry a different token immediately"

    assert slack_oauth.slack_connection_auth_status(
        object(), "org-b", "conn-a", settings,
        environment_name="acceptance",
    ) == "auth_expired"
    assert len(calls) == 3, "Tenant isolation is mandatory"
