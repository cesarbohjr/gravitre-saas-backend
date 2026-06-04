from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.connectors.quickbooks import QuickBooksAPIError, list_invoices, search_customers


def test_list_invoices_query():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"QueryResponse":{"Invoice":[]}}'
    mock_response.json.return_value = {"QueryResponse": {"Invoice": []}}

    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("app.connectors.quickbooks.httpx.Client", return_value=mock_client):
        data = list_invoices("https://sandbox-quickbooks.api.intuit.com/v3/company/1", "token")

    assert "QueryResponse" in data
    params = mock_client.request.call_args[1]["params"]
    assert "select * from Invoice" in params["query"]


def test_list_invoices_raises_on_401():
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_response.json.side_effect = ValueError()

    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("app.connectors.quickbooks.httpx.Client", return_value=mock_client):
        with pytest.raises(QuickBooksAPIError) as exc_info:
            list_invoices("https://quickbooks.api.intuit.com/v3/company/1", "bad-token")

    assert exc_info.value.status_code == 401


def test_search_customers_builds_where_clause():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"QueryResponse":{"Customer":[]}}'
    mock_response.json.return_value = {"QueryResponse": {"Customer": []}}

    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("app.connectors.quickbooks.httpx.Client", return_value=mock_client):
        search_customers(
            "https://quickbooks.api.intuit.com/v3/company/1",
            "token",
            display_name="Acme",
            email="a@b.com",
        )

    params = mock_client.request.call_args[1]["params"]
    assert "DisplayName LIKE '%Acme%'" in params["query"]
    assert "PrimaryEmailAddr = 'a@b.com'" in params["query"]


def test_search_customers_requires_filter():
    with pytest.raises(QuickBooksAPIError) as exc_info:
        search_customers("https://quickbooks.api.intuit.com/v3/company/1", "token")
    assert exc_info.value.status_code == 400
