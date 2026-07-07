"""Tests for Stripe checkout org resolution."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.billing.service import resolve_org_id_from_checkout_metadata

ORG_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
USER_ID = "11111111-2222-3333-4444-555555555555"


def _client_with_tables(table_data: dict[str, list[dict]]) -> MagicMock:
    client = MagicMock()

    def table_factory(name: str) -> MagicMock:
        chain = MagicMock()
        rows = table_data.get(name, [])
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = MagicMock(data=rows)
        return chain

    client.table.side_effect = table_factory
    return client


def test_resolve_org_id_from_metadata_direct():
    client = MagicMock()
    org_id = resolve_org_id_from_checkout_metadata(client, {"org_id": ORG_ID})
    assert org_id == ORG_ID
    client.table.assert_not_called()


def test_resolve_org_id_from_user_id():
    client = _client_with_tables(
        {"organization_members": [{"org_id": ORG_ID}]},
    )
    org_id = resolve_org_id_from_checkout_metadata(client, {"user_id": USER_ID})
    assert org_id == ORG_ID


def test_resolve_org_id_from_checkout_email():
    client = _client_with_tables(
        {"users": [{"org_id": ORG_ID}]},
    )
    org_id = resolve_org_id_from_checkout_metadata(
        client,
        {"checkout_email": "founder@example.com"},
    )
    assert org_id == ORG_ID


def test_resolve_org_id_returns_none_when_unresolved():
    client = _client_with_tables({})
    org_id = resolve_org_id_from_checkout_metadata(client, {"signup_flow": "public_checkout"})
    assert org_id is None


def test_resolve_org_id_from_stripe_customer_org_billing():
    from app.billing.service import resolve_org_id_from_stripe_customer

    client = _client_with_tables(
        {"org_billing": [{"org_id": ORG_ID}]},
    )
    org_id = resolve_org_id_from_stripe_customer(client, "cus_live_123")
    assert org_id == ORG_ID


def test_resolve_org_id_from_stripe_customer_subscriptions_fallback():
    from app.billing.service import resolve_org_id_from_stripe_customer

    client = _client_with_tables(
        {
            "org_billing": [],
            "subscriptions": [{"org_id": ORG_ID}],
        },
    )
    org_id = resolve_org_id_from_stripe_customer(client, "cus_live_456")
    assert org_id == ORG_ID
