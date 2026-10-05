from __future__ import annotations

import httpx
import pytest

from app.connectors.nango_client import create_connect_session, nango_configured, proxy_request
from app.connectors.nango_registry import NANGO_CONNECTOR_REGISTRY, NANGO_CONNECTOR_VENDORS


class _Settings:
    nango_secret_key = "secret"
    nango_api_base_url = "https://api.nango.dev"


def test_registry_is_net_new_and_large_enough() -> None:
    assert len(NANGO_CONNECTOR_VENDORS) >= 35
    for native_candidate in {"notion", "airtable", "xero", "confluence", "linear"}:
        assert native_candidate not in NANGO_CONNECTOR_REGISTRY


def test_nango_configured() -> None:
    settings = _Settings()
    assert nango_configured(settings)
    settings.nango_secret_key = ""
    assert not nango_configured(settings)


def test_create_connect_session(monkeypatch) -> None:
    captured = {}

    def fake_post(self, url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return httpx.Response(
            201,
            json={"data": {"token": "session-token", "expires_at": "2026-10-01T23:00:00Z"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    data = create_connect_session(
        _Settings(),
        end_user_id="user-1",
        end_user_email="user@example.com",
        organization_id="org-1",
        organization_name="Example Org",
        integration_ids=["servicenow"],
        connector_id="connector-123",
    )
    assert data["token"] == "session-token"
    assert captured["url"] == "https://api.nango.dev/connect/sessions"
    assert captured["json"]["allowed_integrations"] == ["servicenow"]
    assert captured["json"]["tags"]["organization_id"] == "org-1"
    assert captured["json"]["tags"]["connector_id"] == "connector-123"


def test_proxy_request_sets_nango_headers(monkeypatch) -> None:
    captured = {}

    def fake_request(self, method, url, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    response = proxy_request(
        _Settings(),
        method="GET",
        endpoint="/api/now/table/incident",
        connection_id="conn-1",
        integration_id="servicenow",
    )
    assert response.status_code == 200
    assert captured["headers"]["Connection-Id"] == "conn-1"
    assert captured["headers"]["Provider-Config-Key"] == "servicenow"



def test_nango_session_tags_do_not_store_provider_credentials(monkeypatch) -> None:
    captured = {}

    def fake_post(self, url, **kwargs):
        captured.update(kwargs)
        return httpx.Response(
            201,
            json={"data": {"token": "session-token"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    create_connect_session(
        _Settings(),
        end_user_id="user-1",
        end_user_email=None,
        organization_id="org-1",
        organization_name=None,
        integration_ids=["freshservice"],
        connector_id="connector-1",
    )
    tags = captured["json"]["tags"]
    assert tags["connector_id"] == "connector-1"
    assert "token" not in tags
    assert "secret" not in tags
    assert "credentials" not in tags


def test_reconnect_preserves_connection_identity_and_attempt(monkeypatch):
    captured = {}
    def fake_post(self, url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(201, json={"data":{"token":"session"}}, request=httpx.Request("POST",url))
    monkeypatch.setattr(httpx.Client, "post", fake_post)
    create_connect_session(_Settings(), end_user_id="u1", end_user_email=None,
                           organization_id="o1", organization_name=None,
                           integration_ids=["freshservice"], connector_id="c1",
                           connection_id="n1", attempt_id="attempt1")
    assert captured["url"].endswith("/connect/sessions/reconnect")
    assert captured["json"]["connection_id"] == "n1"
    assert captured["json"]["integration_id"] == "freshservice"
    assert captured["json"]["tags"]["auth_attempt_id"] == "attempt1"
    assert "allowed_integrations" not in captured["json"]


@pytest.mark.parametrize('status,body,raises',[(200,{'success':True},False),(404,{},False),(200,{'success':False},True),(503,{},True)])
def test_managed_removal_is_idempotent_and_fail_closed(monkeypatch,status,body,raises):
    from app.connectors.nango_client import delete_managed_connection
    captured = {}
    def fake_delete(self,url,**kwargs):
        captured.update(url=url,**kwargs)
        return httpx.Response(status,json=body,request=httpx.Request('DELETE',url))
    monkeypatch.setattr(httpx.Client,'delete',fake_delete)
    if raises:
        with pytest.raises((httpx.HTTPError,ValueError)):
            delete_managed_connection(_Settings(),connection_id='n/1',integration_id='freshservice')
    else:
        delete_managed_connection(_Settings(),connection_id='n/1',integration_id='freshservice')
    assert captured['url'].endswith('/connections/n%2F1')
    assert captured['params'] == {'provider_config_key':'freshservice'}
