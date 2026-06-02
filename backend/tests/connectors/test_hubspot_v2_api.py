from __future__ import annotations

from unittest.mock import patch

import pytest

from app.connectors.hubspot import (
    HubSpotAPIError,
    create_contact,
    create_deal,
    search_contacts,
)


def test_create_contact():
    with patch("app.connectors.hubspot._request") as mock_req:
        mock_req.return_value = {"id": "c-new", "properties": {"email": "new@example.com"}}
        out = create_contact("token", {"email": "new@example.com", "firstname": "Ada"})
    assert out["id"] == "c-new"
    assert mock_req.call_args[0][0] == "POST"


def test_search_contacts_requires_filters():
    with pytest.raises(HubSpotAPIError, match="filter_groups"):
        search_contacts("token", filter_groups=None)


def test_create_deal_associates_contact():
    with patch("app.connectors.hubspot._request") as mock_req:
        with patch("app.connectors.hubspot._associate") as mock_assoc:
            mock_req.return_value = {"id": "deal-9"}
            out = create_deal("token", {"dealname": "Acme"}, contact_id="c-1")
    assert out["id"] == "deal-9"
    mock_assoc.assert_called_once()
