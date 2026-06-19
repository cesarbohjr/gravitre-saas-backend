"""MKT-AUDIT-12.2: Creator payout ledger."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.marketplace.payouts import _split_amounts, get_publisher_payout_summary, record_asset_purchase_payout


def test_split_amounts_uses_platform_fee_bps():
    platform_fee, partner = _split_amounts(10_000, 2000)
    assert platform_fee == 2000
    assert partner == 8000


def test_split_amounts_supports_70_30():
    platform_fee, partner = _split_amounts(10_000, 3000)
    assert platform_fee == 3000
    assert partner == 7000


@patch("app.marketplace.payouts.write_audit_event")
@patch("app.billing.stripe_connect.create_connect_transfer")
def test_maybe_transfer_payout_marks_transferred(mock_transfer, _mock_audit):
    from app.marketplace.payouts import _maybe_transfer_payout

    mock_transfer.return_value = MagicMock(id="tr_test")
    payouts = MagicMock()
    payouts.update.return_value = payouts
    payouts.eq.return_value = payouts
    payouts.execute.return_value = MagicMock(data=[{"id": "payout-1", "status": "transferred"}])
    accounts = MagicMock()
    accounts.select.return_value = accounts
    accounts.eq.return_value = accounts
    accounts.limit.return_value = accounts
    accounts.execute.return_value = MagicMock(
        data=[
            {
                "connect_status": "active",
                "stripe_connect_account_id": "acct_test",
            }
        ]
    )
    client = MagicMock()

    def table(name):
        if name == "marketplace_partner_accounts":
            return accounts
        return payouts

    client.table.side_effect = table
    settings = MagicMock(stripe_secret_key="sk_test")
    _maybe_transfer_payout(
        client,
        settings,
        {
            "id": "payout-1",
            "partner_org_id": "partner-org",
            "partner_earnings_cents": 4000,
            "currency": "usd",
            "asset_id": "asset-1",
        },
    )
    mock_transfer.assert_called_once()


def test_maybe_transfer_payout_stays_pending_without_connect():
    from app.marketplace.payouts import _maybe_transfer_payout

    accounts = MagicMock()
    accounts.select.return_value = accounts
    accounts.eq.return_value = accounts
    accounts.limit.return_value = accounts
    accounts.execute.return_value = MagicMock(data=[])
    client = MagicMock()
    client.table.return_value = accounts
    settings = MagicMock(stripe_secret_key="sk_test")
    _maybe_transfer_payout(
        client,
        settings,
        {
            "id": "payout-1",
            "partner_org_id": "partner-org",
            "partner_earnings_cents": 4000,
            "currency": "usd",
        },
    )
    accounts.update.assert_not_called()


@patch("app.marketplace.payouts._maybe_transfer_payout")
def test_sync_pending_payouts_counts_transfers(mock_transfer):
    from app.marketplace.payouts import sync_pending_payouts

    pending_row = {"id": "payout-1", "status": "pending", "partner_org_id": "partner-org", "partner_earnings_cents": 100}
    payouts = MagicMock()
    payouts.select.return_value = payouts
    payouts.eq.return_value = payouts
    payouts.execute.side_effect = [
        MagicMock(data=[pending_row]),
        MagicMock(data=[{"status": "transferred"}]),
    ]
    client = MagicMock()
    client.table.return_value = payouts
    settings = MagicMock(stripe_secret_key="sk_test")

    result = sync_pending_payouts(client, settings, partner_org_id="partner-org")
    assert result["pendingReviewed"] == 1
    mock_transfer.assert_called_once()


def test_get_publisher_payout_summary():
    payouts = MagicMock()
    payouts.select.return_value = payouts
    payouts.eq.return_value = payouts
    payouts.execute.return_value = MagicMock(
        data=[
            {
                "gross_amount_cents": 5000,
                "platform_fee_cents": 1000,
                "partner_earnings_cents": 4000,
                "status": "transferred",
            },
            {
                "gross_amount_cents": 3000,
                "platform_fee_cents": 600,
                "partner_earnings_cents": 2400,
                "status": "pending",
            },
        ]
    )
    client = MagicMock()
    client.table.return_value = payouts
    summary = get_publisher_payout_summary(client, "partner-org")
    assert summary["grossCents"] == 8000
    assert summary["transferredCents"] == 4000
    assert summary["pendingTransferCents"] == 2400


def test_list_recent_asset_payouts():
    from app.marketplace.payouts import list_recent_asset_payouts

    payouts = MagicMock()
    payouts.select.return_value = payouts
    payouts.eq.return_value = payouts
    payouts.order.return_value = payouts
    payouts.limit.return_value = payouts
    payouts.execute.return_value = MagicMock(
        data=[
            {
                "id": "payout-1",
                "asset_id": "asset-1",
                "gross_amount_cents": 5000,
                "partner_earnings_cents": 4000,
                "status": "transferred",
                "currency": "usd",
                "created_at": "2026-06-19T00:00:00Z",
                "marketplace_assets": {"slug": "sales-pack", "title": "Sales Pack"},
            }
        ]
    )
    client = MagicMock()
    client.table.return_value = payouts
    rows = list_recent_asset_payouts(client, "partner-org")
    assert rows[0]["assetSlug"] == "sales-pack"
    assert rows[0]["partnerEarningsCents"] == 4000


@patch("app.marketplace.payouts.write_audit_event")
@patch("app.marketplace.payouts._maybe_transfer_payout")
@patch("app.marketplace.payouts._load_publisher_id", return_value=("pub-1", "partner-org"))
def test_record_asset_purchase_payout(mock_publisher, mock_transfer, _mock_audit):
    inserted = MagicMock()
    inserted.insert.return_value = inserted
    inserted.execute.return_value = MagicMock(
        data=[
            {
                "id": "payout-1",
                "partner_org_id": "partner-org",
                "partner_earnings_cents": 800,
                "currency": "usd",
            }
        ]
    )
    client = MagicMock()
    client.table.return_value = inserted
    settings = MagicMock(marketplace_platform_fee_bps=2000, stripe_secret_key="sk_test")
    row = record_asset_purchase_payout(
        client,
        settings,
        org_id="buyer-org",
        asset_id="asset-1",
        entitlement_id="ent-1",
        gross_cents=1000,
        currency="usd",
    )
    assert row["id"] == "payout-1"
    mock_transfer.assert_called_once()
