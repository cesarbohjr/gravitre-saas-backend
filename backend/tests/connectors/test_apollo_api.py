"""Apollo API client."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.connectors.apollo_api import ApolloAPIError, resolve_apollo_api_key, search_people, verify_apollo_api_key


def test_search_people_uses_x_api_key_header():
    with patch("app.connectors.apollo_api.httpx.Client") as client_cls:
        response = MagicMock(status_code=200, text='{"people":[]}')
        response.json.return_value = {"people": []}
        client_cls.return_value.__enter__.return_value.request.return_value = response
        out = search_people("secret-key", params={"per_page": 1})
    assert out == {"people": []}
    headers = client_cls.return_value.__enter__.return_value.request.call_args[1]["headers"]
    assert headers["X-Api-Key"] == "secret-key"


def test_verify_apollo_api_key_false_on_401():
    with patch("app.connectors.apollo_api.search_people", side_effect=ApolloAPIError("bad", status_code=401)):
        assert verify_apollo_api_key("bad") is False


@patch("app.connectors.apollo_api.get_decrypted_secret")
@patch("app.connectors.apollo_api.get_connector")
def test_resolve_apollo_api_key(mock_get, mock_secret):
    mock_get.return_value = {"id": "c1"}
    mock_secret.side_effect = lambda _c, _id, key, _s: "token" if key == "api_token" else None
    settings = MagicMock()
    cid, key = resolve_apollo_api_key(MagicMock(), "org", "c1", settings)
    assert cid == "c1"
    assert key == "token"
