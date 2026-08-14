"""Clay API client."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.connectors.clay_api import (
    ClayAPIError,
    enrich_person,
    list_tables,
    push_to_webhook,
    resolve_clay_api_key,
)


def test_enrich_person_uses_bearer_auth():
    with patch("app.connectors.clay_api.httpx.Client") as client_cls:
        response = MagicMock(status_code=200, text='{"name":"Ada"}')
        response.json.return_value = {"name": "Ada"}
        client_cls.return_value.__enter__.return_value.request.return_value = response
        out = enrich_person("secret-key", email="ada@example.com")
    assert out == {"name": "Ada"}
    call = client_cls.return_value.__enter__.return_value.request.call_args
    assert call[1]["headers"]["Authorization"] == "Bearer secret-key"
    assert call[0][0] == "POST"
    assert call[0][1].endswith("/v1/people/enrich")


def test_list_tables_from_webhook_config():
    data = list_tables({"webhook_url": "https://app.clay.com/api/v1/webhooks/abc", "table_name": "Leads"})
    assert len(data["tables"]) == 1
    assert data["tables"][0]["webhook_url"] == "https://app.clay.com/api/v1/webhooks/abc"


def test_push_to_webhook_posts_json():
    with patch("app.connectors.clay_api.httpx.Client") as client_cls:
        response = MagicMock(status_code=200, content=b"{}")
        response.json.return_value = {}
        client_cls.return_value.__enter__.return_value.post.return_value = response
        out = push_to_webhook("https://app.clay.com/api/v1/webhooks/abc", payload={"email": "a@b.com"})
    assert out["submitted"] == 1
    client_cls.return_value.__enter__.return_value.post.assert_called_once()


@patch("app.connectors.clay_api.get_decrypted_secret")
@patch("app.connectors.clay_api.get_connector")
def test_resolve_clay_api_key(mock_get, mock_secret):
    mock_get.return_value = {"id": "c1", "config": {}}
    mock_secret.side_effect = lambda _c, _id, key, _s: "token" if key == "api_key" else None
    settings = MagicMock()
    cid, key = resolve_clay_api_key(MagicMock(), "org", "c1", settings)
    assert cid == "c1"
    assert key == "token"


def test_push_to_webhook_requires_url():
    try:
        push_to_webhook("", payload={"email": "a@b.com"})
    except ClayAPIError as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("expected ClayAPIError")


def test_push_rejects_shared_workbook_page_url():
    try:
        push_to_webhook(
            "https://app.clay.com/shared-workbook/share_abc",
            payload={"email": "a@b.com"},
        )
    except ClayAPIError as exc:
        assert exc.status_code == 400
        assert "shared workbook" in str(exc).lower()
    else:
        raise AssertionError("expected ClayAPIError")
