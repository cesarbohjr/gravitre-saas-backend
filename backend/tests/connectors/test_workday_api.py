from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.connectors.workday import (
    WorkdayAPIError,
    get_worker,
    list_org_units,
    list_positions,
    normalize_worker,
)


def test_normalize_worker_extracts_email():
    worker = normalize_worker(
        {
            "id": "w1",
            "descriptor": "Jane Doe",
            "emails": [{"email": "jane@example.com"}],
            "businessTitle": "HR Partner",
        }
    )
    assert worker["id"] == "w1"
    assert worker["email"] == "jane@example.com"
    assert worker["business_title"] == "HR Partner"


def test_get_worker_by_id_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"id":"w1","descriptor":"Jane Doe"}'
    mock_response.json.return_value = {"id": "w1", "descriptor": "Jane Doe"}
    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("app.connectors.workday.httpx.Client", return_value=mock_client):
        worker = get_worker(
            "https://impl.wd12.myworkday.com/ccx/api/v1/acme",
            "token",
            worker_id="w1",
        )
    assert worker["id"] == "w1"


def test_list_org_units_api_error():
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "unauthorized"
    mock_response.json.side_effect = ValueError("not json")
    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("app.connectors.workday.httpx.Client", return_value=mock_client):
        try:
            list_org_units("https://impl.wd12.myworkday.com/ccx/api/v1/acme", "bad-token")
            raised = False
        except WorkdayAPIError:
            raised = True
    assert raised is True


def test_list_positions_requires_no_params():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"data":[{"id":"p1","descriptor":"Engineer"}]}'
    mock_response.json.return_value = {"data": [{"id": "p1", "descriptor": "Engineer"}]}
    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("app.connectors.workday.httpx.Client", return_value=mock_client):
        result = list_positions("https://impl.wd12.myworkday.com/ccx/api/v1/acme", "token", limit=10)
    assert result["total"] == 1
    assert result["positions"][0]["id"] == "p1"
