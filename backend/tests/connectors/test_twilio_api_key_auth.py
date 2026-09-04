"""Tests for Twilio API key auth and account resolution."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.connectors.twilio_api import _auth_header, fetch_twilio_account_sid
from app.services.tool_types import ToolContext, ToolValidationError


def test_auth_header_uses_api_key_when_present() -> None:
    ctx = ToolContext(
        client=MagicMock(), org_id="org", connector_id="cid", actor_id="user", settings=MagicMock()
    )
    conn = {"config": {"api_key_sid": "SK123", "account_sid": "AC123"}}
    with patch("app.connectors.twilio_api.get_decrypted_secret") as gs:
        gs.side_effect = lambda _c, _cid, key, _s: {
            "api_key_sid": "SK123",
            "api_key_secret": "secret",
        }.get(key, "")
        header = _auth_header(ctx, "cid", "AC123", conn)
    assert header.startswith("Basic ")
    import base64

    decoded = base64.b64decode(header.removeprefix("Basic ")).decode()
    assert decoded == "SK123:secret"


def test_fetch_twilio_account_sid_parses_first_account() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"accounts":[{"sid":"ACabc123"}]}'
    mock_resp.json.return_value = {"accounts": [{"sid": "ACabc123"}]}
    with patch("app.connectors.twilio_api.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        sid = fetch_twilio_account_sid(api_key_sid="SKx", api_key_secret="sec")
    assert sid == "ACabc123"


def test_fetch_twilio_account_sid_requires_credentials() -> None:
    with pytest.raises(ToolValidationError):
        fetch_twilio_account_sid(api_key_sid="", api_key_secret="")
