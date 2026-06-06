"""Marketplace billing service tests (STA-96)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.marketplace_billing_service import (
    _split_amounts,
    get_partner_earnings_summary,
    record_marketplace_usage_for_invoke,
    upsert_connector_pricing,
)

REGISTRY_ID = "10000000-0000-0000-0000-000000000001"
PARTNER_ORG = "20000000-0000-0000-0000-000000000002"
CUSTOMER_ORG = "30000000-0000-0000-0000-000000000003"


def test_split_amounts_applies_platform_fee():
    platform_fee, partner = _split_amounts(1000, 2000)
    assert platform_fee == 200
    assert partner == 800


@patch("app.services.marketplace_billing_service._maybe_transfer_partner_earnings")
@patch("app.services.marketplace_billing_service.get_pricing_for_vendor")
def test_record_usage_for_per_invocation(mock_pricing, _mock_transfer):
    mock_pricing.return_value = {
        "registryId": REGISTRY_ID,
        "partnerOrgId": PARTNER_ORG,
        "pricingModel": "per_invocation",
        "priceCents": 50,
        "currency": "usd",
        "platformFeeBps": 2000,
    }
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "usage-1",
                "partner_org_id": PARTNER_ORG,
                "partner_earnings_cents": 40,
            }
        ]
    )
    settings = SimpleNamespace(stripe_secret_key="", marketplace_platform_fee_bps=2000)
    result = record_marketplace_usage_for_invoke(
        client,
        settings,
        customer_org_id=CUSTOMER_ORG,
        connector_id="conn-1",
        vendor="acme_tools",
        action="acme_tools.tickets.list",
        idempotency_key="key-1",
    )
    assert result is not None
    insert_row = client.table.return_value.insert.call_args[0][0]
    assert insert_row["gross_amount_cents"] == 50
    assert insert_row["platform_fee_cents"] == 10
    assert insert_row["partner_earnings_cents"] == 40


@patch("app.services.marketplace_billing_service.get_pricing_for_vendor", return_value=None)
def test_record_usage_skips_unknown_vendor(_mock_pricing):
    client = MagicMock()
    settings = SimpleNamespace(stripe_secret_key="", marketplace_platform_fee_bps=2000)
    assert (
        record_marketplace_usage_for_invoke(
            client,
            settings,
            customer_org_id=CUSTOMER_ORG,
            connector_id="conn-1",
            vendor="unknown",
            action="unknown.action",
            idempotency_key="key-2",
        )
        is None
    )


def test_get_partner_earnings_summary_totals():
    client = MagicMock()
    usage_chain = MagicMock()
    usage_chain.select.return_value = usage_chain
    usage_chain.eq.return_value = usage_chain
    usage_chain.execute.return_value = MagicMock(
        data=[
            {
                "gross_amount_cents": 100,
                "platform_fee_cents": 20,
                "partner_earnings_cents": 80,
                "transfer_status": "transferred",
            },
            {
                "gross_amount_cents": 50,
                "platform_fee_cents": 10,
                "partner_earnings_cents": 40,
                "transfer_status": "pending",
            },
        ]
    )
    install_chain = MagicMock()
    install_chain.select.return_value = install_chain
    install_chain.eq.return_value = install_chain
    install_chain.execute.return_value = MagicMock(data=[{"id": "i1"}], count=1)

    def table_side_effect(name):
        if name == "marketplace_usage_events":
            return usage_chain
        if name == "marketplace_connector_installs":
            return install_chain
        return MagicMock()

    client.table.side_effect = table_side_effect
    summary = get_partner_earnings_summary(client, PARTNER_ORG)
    assert summary["grossCents"] == 150
    assert summary["partnerEarningsCents"] == 120
    assert summary["transferredCents"] == 80
    assert summary["pendingTransferCents"] == 40
    assert summary["usageEventCount"] == 2
    assert summary["activeInstallCount"] == 1


@patch("app.services.marketplace_billing_service._get_partner_account_row")
@patch("app.services.marketplace_billing_service._get_registry_for_partner")
def test_upsert_pricing_requires_connect_for_paid(mock_registry, mock_account):
    mock_registry.return_value = {"id": REGISTRY_ID, "vendor": "acme_tools", "name": "Acme"}
    mock_account.return_value = {"connect_status": "onboarding"}
    client = MagicMock()
    settings = SimpleNamespace(marketplace_platform_fee_bps=2000)
    with pytest.raises(HTTPException) as exc:
        upsert_connector_pricing(
            client,
            settings,
            partner_org_id=PARTNER_ORG,
            registry_id=REGISTRY_ID,
            pricing_model="per_invocation",
            price_cents=25,
        )
    assert exc.value.status_code == 409
