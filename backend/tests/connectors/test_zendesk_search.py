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
