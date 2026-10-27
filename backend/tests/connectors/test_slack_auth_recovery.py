from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from app.connectors import slack_oauth as slack


@pytest.fixture
def probe(monkeypatch):
    slack._rejected_tokens.clear()
    monkeypatch.setattr("app.connectors.managed_oauth.managed_oauth_row", lambda *_a, **_k: None)
    monkeypatch.setattr(slack, "get_decrypted_secret", lambda *_a, **_k: "synthetic-token")
    http = MagicMock()
    monkeypatch.setattr(slack.httpx, "Client", lambda **_: http)
    post = http.__enter__.return_value.post
    settings = SimpleNamespace(slack_client_id="id", slack_client_secret="secret")
    def run():
        return slack.slack_connection_auth_status(MagicMock(), "org", "connector", settings, environment_name="production")
    yield run, post
    slack._rejected_tokens.clear()


def response(status, data):
    return httpx.Response(status, json=data, request=httpx.Request("POST", slack.SLACK_AUTH_TEST_URL))


def test_rejected_token_is_not_polled_repeatedly_and_new_token_recovers(probe, monkeypatch):
    run, post = probe
    post.return_value = response(200, {"ok": False, "error": "invalid_auth"})
    assert run() == "auth_expired"
    assert run() == "auth_expired"
    assert post.call_count == 1
    monkeypatch.setattr(slack, "get_decrypted_secret", lambda *_a, **_k: "replacement-token")
    post.return_value = response(200, {"ok": True})
    assert run() == "connected"
    assert post.call_count == 2


@pytest.mark.parametrize("status,data", [(503, {}), (429, {}), (200, {"ok": False, "error": "internal_error"})])
def test_transient_errors_are_not_reported_or_cached_as_revocation(probe, status, data):
    run, post = probe
    post.return_value = response(status, data)
    assert run() == "temporarily_unavailable"
    post.return_value = response(200, {"ok": True})
    assert run() == "connected"
    assert not slack._rejected_tokens
