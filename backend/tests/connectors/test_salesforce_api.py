from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.connectors.salesforce import SalesforceAPIError, get_lead, search_leads, update_opportunity_stage


def test_get_lead_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"Id":"00Q1","Status":"Open"}'
    mock_response.json.return_value = {"Id": "00Q1", "Status": "Open"}

    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("app.connectors.salesforce.httpx.Client", return_value=mock_client):
        data = get_lead("https://example.my.salesforce.com", "token", "00Q1")

    assert data["Id"] == "00Q1"
    call_args = mock_client.request.call_args
    assert call_args[0][0] == "GET"
    assert "/sobjects/Lead/00Q1" in call_args[0][1]


def test_update_opportunity_stage_maps_stage_name():
    mock_response = MagicMock()
    mock_response.status_code = 204
    mock_response.text = ""

    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("app.connectors.salesforce.httpx.Client", return_value=mock_client):
        result = update_opportunity_stage(
            "https://example.my.salesforce.com",
            "token",
            "006xx",
            "Closed Won",
        )

    assert result == {}
    body = mock_client.request.call_args[1]["json"]
    assert body == {"StageName": "Closed Won"}


def test_get_lead_raises_on_404():
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = '[{"message":"Not Found"}]'
    mock_response.json.return_value = [{"message": "Not Found"}]

    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("app.connectors.salesforce.httpx.Client", return_value=mock_client):
        with pytest.raises(SalesforceAPIError) as exc_info:
            get_lead("https://example.my.salesforce.com", "token", "bad-id")

    assert exc_info.value.status_code == 404


def test_search_leads_builds_soql():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"records":[]}'
    mock_response.json.return_value = {"records": []}

    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("app.connectors.salesforce.httpx.Client", return_value=mock_client):
        search_leads(
            "https://example.my.salesforce.com",
            "token",
            email="a@b.com",
            company="Acme",
        )

    params = mock_client.request.call_args[1]["params"]
    assert "Email = 'a@b.com'" in params["q"]
    assert "Company = 'Acme'" in params["q"]
