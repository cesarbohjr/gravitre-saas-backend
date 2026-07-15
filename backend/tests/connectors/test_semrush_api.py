"""SEMrush API client tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.connectors.semrush_api import (
    SemrushAPIError,
    backlinks_list,
    domain_overview,
    keywords_list,
    resolve_semrush_connector,
)


def test_domain_overview_parses_semicolon_table():
    body = "Database;Domain;Rank\nus;example.com;12\n"
    with patch("app.connectors.semrush_api.httpx.Client") as client_cls:
        response = MagicMock(status_code=200, text=body)
        client_cls.return_value.__enter__.return_value.get.return_value = response
        out = domain_overview("secret-key", domain="example.com", database="us")
    assert out["row_count"] == 1
    assert out["rows"][0]["Domain"] == "example.com"
    call = client_cls.return_value.__enter__.return_value.get.call_args
    assert call[1]["params"]["key"] == "secret-key"
    assert call[1]["params"]["type"] == "domain_ranks"


def test_keywords_list_uses_domain_organic():
    body = "Keyword;Position\nsaas tools;3\n"
    with patch("app.connectors.semrush_api.httpx.Client") as client_cls:
        response = MagicMock(status_code=200, text=body)
        client_cls.return_value.__enter__.return_value.get.return_value = response
        out = keywords_list("secret-key", domain="example.com", limit=5)
    assert out["row_count"] == 1
    call = client_cls.return_value.__enter__.return_value.get.call_args
    assert call[1]["params"]["type"] == "domain_organic"
    assert call[1]["params"]["display_limit"] == 5


def test_backlinks_list_hits_analytics_v1():
    body = "source_url;target_url\nhttps://a.com;https://b.com\n"
    with patch("app.connectors.semrush_api.httpx.Client") as client_cls:
        response = MagicMock(status_code=200, text=body)
        client_cls.return_value.__enter__.return_value.get.return_value = response
        out = backlinks_list("secret-key", target="example.com", limit=10)
    assert out["row_count"] == 1
    call = client_cls.return_value.__enter__.return_value.get.call_args
    assert "analytics/v1" in call[0][0]
    assert call[1]["params"]["type"] == "backlinks"


def test_semrush_error_line_raises():
    with patch("app.connectors.semrush_api.httpx.Client") as client_cls:
        response = MagicMock(status_code=200, text="ERROR 43 :: ERROR 43 :: API KEY INVALID")
        client_cls.return_value.__enter__.return_value.get.return_value = response
        try:
            domain_overview("bad", domain="example.com")
        except SemrushAPIError as exc:
            assert "ERROR" in str(exc)
        else:
            raise AssertionError("expected SemrushAPIError")


@patch("app.connectors.semrush_api.get_decrypted_secret")
@patch("app.connectors.semrush_api.get_connector")
def test_resolve_semrush_connector(mock_get, mock_secret):
    mock_get.return_value = {"id": "c1", "config": {}}
    mock_secret.side_effect = lambda _c, _id, key, _s: "token" if key == "api_key" else None
    cid, key = resolve_semrush_connector(MagicMock(), "org", "c1", MagicMock())
    assert cid == "c1"
    assert key == "token"
