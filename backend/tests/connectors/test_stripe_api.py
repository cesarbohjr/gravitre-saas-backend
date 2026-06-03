from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import stripe

from app.connectors.stripe_api import (
    StripeAPIError,
    list_invoices,
    resolve_stripe_credentials,
)


def test_resolve_stripe_credentials_from_connector_secret():
    settings = SimpleNamespace(
        connector_secrets_encryption_key="a" * 32,
        encryption_key="",
    )
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "conn-1",
                "org_id": "org-1",
                "type": "stripe",
                "config": {"stripe_account_id": "acct_123"},
                "api_key_encrypted": None,
            }
        ]
    )
    with patch(
        "app.connectors.stripe_api.get_decrypted_secret",
        return_value="sk_test_abc",
    ):
        key, account = resolve_stripe_credentials(client, "org-1", "conn-1", settings)
    assert key == "sk_test_abc"
    assert account == "acct_123"


def test_list_invoices_calls_stripe():
    mock_list = MagicMock()
    mock_list.to_dict.return_value = {"data": [{"id": "in_1"}]}
    with patch("app.connectors.stripe_api.stripe.Invoice.list", return_value=mock_list) as listed:
        result = list_invoices(
            "sk_test",
            stripe_account="acct_x",
            customer_id="cus_1",
            status="open",
            limit=5,
        )
    assert result["data"][0]["id"] == "in_1"
    listed.assert_called_once()
    kwargs = listed.call_args.kwargs
    assert kwargs["api_key"] == "sk_test"
    assert kwargs["stripe_account"] == "acct_x"
    assert kwargs["customer"] == "cus_1"
    assert kwargs["status"] == "open"
    assert kwargs["limit"] == 5


def test_list_invoices_maps_auth_error():
    with patch(
        "app.connectors.stripe_api.stripe.Invoice.list",
        side_effect=stripe.error.AuthenticationError("bad key"),
    ):
        with pytest.raises(StripeAPIError) as exc_info:
            list_invoices("sk_bad")
    assert exc_info.value.status_code == 401
