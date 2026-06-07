from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.connectors.marketo import MarketoAPIError, get_lead, list_campaigns, update_leads


def test_get_lead_requires_identifier():
    with pytest.raises(MarketoAPIError):
        get_lead("token", "mid")


def test_get_lead_by_email():
    with patch("app.connectors.marketo._request", return_value={"result": [{"id": 1}]}) as req:
        data = get_lead("token", "mid", email="lead@example.com")
    assert data["result"][0]["id"] == 1
    req.assert_called_once()
    assert req.call_args.kwargs["params"]["filterType"] == "email"


def test_update_leads_posts_payload():
    with patch("app.connectors.marketo._request", return_value={"result": [{"status": "updated"}]}) as req:
        data = update_leads(
            "token",
            "mid",
            action="updateOnly",
            leads=[{"email": "lead@example.com", "firstName": "Pat"}],
        )
    assert data["result"][0]["status"] == "updated"
    body = req.call_args.kwargs["json_body"]
    assert body["action"] == "updateOnly"
    assert body["input"][0]["email"] == "lead@example.com"


def test_list_campaigns():
    with patch("app.connectors.marketo._request", return_value={"result": []}) as req:
        list_campaigns("token", "mid", max_return=10)
    assert req.call_args.kwargs["params"]["maxReturn"] == 10
