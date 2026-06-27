from __future__ import annotations

from unittest.mock import patch

from app.connectors.zendesk import list_resolved_tickets_since


def test_list_resolved_tickets_since():
    with patch("app.connectors.zendesk._request") as req:
        req.return_value = {
            "results": [
                {"id": 9, "subject": "Help", "description": "Body", "status": "solved"},
            ]
        }
        tickets = list_resolved_tickets_since("acme", "a@b.com", "tok", since_date="2026-06-01")
    assert len(tickets) == 1
    assert tickets[0]["id"] == 9
    params = req.call_args[1]["params"]
    assert "status:solved" in params["query"]


def test_list_tickets():
    from app.connectors.zendesk import list_tickets

    with patch("app.connectors.zendesk._request") as req:
        req.return_value = {"tickets": [{"id": 1, "subject": "Open"}]}
        tickets = list_tickets("acme", None, None, oauth_access_token="oauth", status="open", limit=10)
    assert tickets[0]["id"] == 1
    assert req.call_args[0][4] == "/tickets.json"
    assert req.call_args[1]["params"]["status"] == "open"


def test_get_user():
    from app.connectors.zendesk import get_user

    with patch("app.connectors.zendesk._request") as req:
        req.return_value = {"user": {"id": 42, "name": "Agent"}}
        user = get_user("acme", None, None, 42, oauth_access_token="oauth")
    assert user["id"] == 42
    assert "/users/42.json" in req.call_args[0][4]
