from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.connectors.hubspot import (
    HubSpotAPIError,
    create_list,
    get_contact,
    normalize_hubspot_list_processing_type,
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


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("STATIC", "MANUAL"),
        ("standard", "MANUAL"),
        ("default", "MANUAL"),
        ("DYNAMIC", "MANUAL"),  # no filterBranch → static list
        ("MANUAL", "MANUAL"),
        ("SNAPSHOT", "SNAPSHOT"),
        ("not-a-type", "MANUAL"),
    ],
)
def test_hubspot_list_processing_type_aliases(raw: str, expected: str) -> None:
    assert normalize_hubspot_list_processing_type(raw) == expected


def test_hubspot_dynamic_kept_when_filter_branch_present() -> None:
    assert (
        normalize_hubspot_list_processing_type("DYNAMIC", has_filter_branch=True)
        == "DYNAMIC"
    )


def test_create_list_sends_manual_for_static_alias():
    with patch("app.connectors.hubspot._request") as mock_req:
        mock_req.return_value = {"listId": "1"}
        create_list("token", "MSPs", processing_type="STATIC")
    body = mock_req.call_args[1]["json_body"]
    assert body["processingType"] == "MANUAL"
    assert body["objectTypeId"] == "0-1"
    assert body["name"] == "MSPs"
