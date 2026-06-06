from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.connectors.netsuite import (
    NetSuiteAPIError,
    create_journal_entry_draft,
    list_invoices,
    update_customer_billing_contact,
)


def test_list_invoices_pagination():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"items":[]}'
    mock_response.json.return_value = {"items": []}

    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("app.connectors.netsuite.httpx.Client", return_value=mock_client):
        data = list_invoices(
            "https://1234567.suitetalk.api.netsuite.com/services/rest/record/v1",
            "token",
            limit=10,
            offset=5,
        )

    assert data["items"] == []
    params = mock_client.request.call_args[1]["params"]
    assert params["limit"] == 10
    assert params["offset"] == 5


def test_list_invoices_raises_on_401():
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_response.json.side_effect = ValueError()

    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("app.connectors.netsuite.httpx.Client", return_value=mock_client):
        with pytest.raises(NetSuiteAPIError) as exc_info:
            list_invoices(
                "https://1234567.suitetalk.api.netsuite.com/services/rest/record/v1",
                "bad-token",
            )

    assert exc_info.value.status_code == 401


def test_update_customer_billing_contact_filters_fields():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"id":"1"}'
    mock_response.json.return_value = {"id": "1"}

    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("app.connectors.netsuite.httpx.Client", return_value=mock_client):
        update_customer_billing_contact(
            "https://1234567.suitetalk.api.netsuite.com/services/rest/record/v1",
            "token",
            "1",
            {"email": "a@b.com", "creditLimit": 9999},
        )

    body = mock_client.request.call_args[1]["json"]
    assert body == {"email": "a@b.com"}
    assert "creditLimit" not in body


def test_update_customer_billing_contact_requires_allowed_fields():
    with pytest.raises(NetSuiteAPIError) as exc_info:
        update_customer_billing_contact(
            "https://1234567.suitetalk.api.netsuite.com/services/rest/record/v1",
            "token",
            "1",
            {"creditLimit": 9999},
        )
    assert exc_info.value.status_code == 400


def test_create_journal_entry_draft_sets_flags():
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.text = '{"id":"99"}'
    mock_response.json.return_value = {"id": "99"}

    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("app.connectors.netsuite.httpx.Client", return_value=mock_client):
        create_journal_entry_draft(
            "https://1234567.suitetalk.api.netsuite.com/services/rest/record/v1",
            "token",
            {"memo": "test"},
        )

    body = mock_client.request.call_args[1]["json"]
    assert body["approved"] is False
    assert body["draft"] is True
    assert body["memo"] == "test"
