from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.connectors.hubspot import (
    HubSpotAPIError,
    get_contact,
    update_deal_stage,
)


def test_get_contact_by_id():
    with patch("app.connectors.hubspot._request") as mock_req:
        mock_req.return_value = {"id": "1", "properties": {"email": "a@b.com"}}
        out = get_contact("token", contact_id="1")
    assert out["id"] == "1"
    mock_req.assert_called_once()
    assert "/contacts/1" in mock_req.call_args[0][1]


def test_get_contact_requires_identifier():
    with pytest.raises(HubSpotAPIError, match="contact_id or email"):
        get_contact("token")


def test_update_deal_stage():
    with patch("app.connectors.hubspot._request") as mock_req:
        mock_req.return_value = {"id": "deal-1", "properties": {"dealstage": "qualified"}}
        out = update_deal_stage("token", "deal-1", "qualified")
    assert out["id"] == "deal-1"
    body = mock_req.call_args[1]["json_body"]
    assert body["properties"]["dealstage"] == "qualified"
