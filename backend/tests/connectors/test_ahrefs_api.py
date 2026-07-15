"""Ahrefs API client tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.connectors.ahrefs_api import (
    AhrefsAPIError,
    backlinks_list,
    domain_rating,
    keywords_list,
    resolve_ahrefs_connector,
)


def test_domain_rating_bearer_auth():
    with patch("app.connectors.ahrefs_api.httpx.Client") as client_cls:
        response = MagicMock(status_code=200, text='{"domain_rating":72}', content=b'{"domain_rating":72}')
        response.json.return_value = {"domain_rating": 72}
        client_cls.return_value.__enter__.return_value.request.return_value = response
        out = domain_rating("secret-key", target="example.com", report_date="2026-07-01")
    assert out["data"]["domain_rating"] == 72
    call = client_cls.return_value.__enter__.return_value.request.call_args
    assert call[0][0] == "GET"
    assert call[1]["headers"]["Authorization"] == "Bearer secret-key"
    assert call[0][1].endswith("/site-explorer/domain-rating")


def test_keywords_list_organic_keywords():
    payload = {"keywords": [{"keyword": "saas", "volume": 1000}]}
    with patch("app.connectors.ahrefs_api.httpx.Client") as client_cls:
        response = MagicMock(status_code=200, text="{}", content=b"{}")
        response.json.return_value = payload
        client_cls.return_value.__enter__.return_value.request.return_value = response
        out = keywords_list("secret-key", target="example.com", limit=5)
    assert out["row_count"] == 1
    call = client_cls.return_value.__enter__.return_value.request.call_args
    assert call[0][1].endswith("/site-explorer/organic-keywords")
    assert call[1]["params"]["limit"] == 5


def test_backlinks_list_all_backlinks():
    payload = {"backlinks": [{"url_from": "https://a.com"}]}
    with patch("app.connectors.ahrefs_api.httpx.Client") as client_cls:
        response = MagicMock(status_code=200, text="{}", content=b"{}")
        response.json.return_value = payload
        client_cls.return_value.__enter__.return_value.request.return_value = response
        out = backlinks_list("secret-key", target="example.com", limit=3)
    assert out["row_count"] == 1
    call = client_cls.return_value.__enter__.return_value.request.call_args
    assert call[0][1].endswith("/site-explorer/all-backlinks")


def test_ahrefs_http_error():
    with patch("app.connectors.ahrefs_api.httpx.Client") as client_cls:
        response = MagicMock(status_code=401, text="unauthorized", content=b"unauthorized")
        client_cls.return_value.__enter__.return_value.request.return_value = response
        try:
            domain_rating("bad", target="example.com")
        except AhrefsAPIError as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("expected AhrefsAPIError")


@patch("app.connectors.ahrefs_api.get_decrypted_secret")
@patch("app.connectors.ahrefs_api.get_connector")
def test_resolve_ahrefs_connector(mock_get, mock_secret):
    mock_get.return_value = {"id": "c1", "config": {}}
    mock_secret.side_effect = lambda _c, _id, key, _s: "token" if key == "api_token" else None
    cid, key = resolve_ahrefs_connector(MagicMock(), "org", "c1", MagicMock())
    assert cid == "c1"
    assert key == "token"
