from __future__ import annotations

from unittest.mock import patch

from app.connectors.hubspot import list_notes_since


def test_list_notes_since_calls_search():
    with patch("app.connectors.hubspot._request") as req:
        req.return_value = {"results": [{"id": "1", "properties": {"hs_note_body": "x"}}]}
        items = list_notes_since("tok", since_ms=1000, limit=10)
    assert len(items) == 1
    call = req.call_args
    assert call[0][1] == "/crm/v3/objects/notes/search"
    body = call[1]["json_body"]
    assert body["filterGroups"][0]["filters"][0]["value"] == "1000"
