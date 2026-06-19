"""MKT-AUDIT-14.1: Publisher revenue analytics aggregation."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.marketplace.publisher_analytics import (
    _sum_earnings,
    get_publisher_revenue_analytics,
    top_assets_by_earnings,
)


def test_sum_earnings_combines_connector_and_asset_streams():
    combined = _sum_earnings(
        {
            "grossCents": 1000,
            "platformFeeCents": 200,
            "partnerEarningsCents": 800,
            "transferredCents": 500,
            "pendingTransferCents": 300,
        },
        {
            "grossCents": 500,
            "platformFeeCents": 100,
            "partnerEarningsCents": 400,
            "transferredCents": 400,
            "pendingTransferCents": 0,
        },
    )
    assert combined["grossCents"] == 1500
    assert combined["partnerEarningsCents"] == 1200
    assert combined["transferredCents"] == 900
    assert combined["pendingTransferCents"] == 300


def test_top_assets_by_earnings_ranks_by_partner_share():
    payouts = MagicMock()
    payouts.select.return_value = payouts
    payouts.eq.return_value = payouts
    payouts.execute.return_value = MagicMock(
        data=[
            {
                "asset_id": "asset-a",
                "gross_amount_cents": 1000,
                "partner_earnings_cents": 800,
                "marketplace_assets": {"slug": "pack-a", "title": "Pack A"},
            },
            {
                "asset_id": "asset-b",
                "gross_amount_cents": 2000,
                "partner_earnings_cents": 1600,
                "marketplace_assets": {"slug": "pack-b", "title": "Pack B"},
            },
            {
                "asset_id": "asset-a",
                "gross_amount_cents": 500,
                "partner_earnings_cents": 400,
                "marketplace_assets": {"slug": "pack-a", "title": "Pack A"},
            },
        ]
    )
    client = MagicMock()
    client.table.return_value = payouts

    rows = top_assets_by_earnings(client, "partner-org", limit=5)
    assert rows[0]["assetId"] == "asset-b"
    assert rows[0]["partnerEarningsCents"] == 1600
    assert rows[1]["assetId"] == "asset-a"
    assert rows[1]["partnerEarningsCents"] == 1200
    assert rows[1]["saleCount"] == 2


@patch("app.marketplace.publisher_analytics.platform_top_earning_assets", return_value=[])
@patch("app.marketplace.publisher_analytics.list_recent_usage_events", return_value=[])
@patch(
    "app.marketplace.publisher_analytics.list_recent_asset_payouts",
    return_value=[{"id": "payout-1"}],
)
@patch(
    "app.marketplace.publisher_analytics.top_assets_by_earnings",
    return_value=[{"assetId": "asset-a", "partnerEarningsCents": 500}],
)
@patch("app.marketplace.publisher_analytics._publisher_asset_adoption")
@patch("app.marketplace.publisher_analytics.get_publisher_payout_summary")
@patch("app.marketplace.publisher_analytics.get_partner_earnings_summary")
def test_get_publisher_revenue_analytics_shapes_payload(
    mock_usage,
    mock_asset_sales,
    mock_adoption,
    _mock_top,
    _mock_recent_payouts,
    _mock_recent_usage,
    _mock_platform_top,
):
    mock_usage.return_value = {
        "grossCents": 3000,
        "platformFeeCents": 600,
        "partnerEarningsCents": 2400,
        "transferredCents": 2000,
        "pendingTransferCents": 400,
        "usageEventCount": 12,
        "activeInstallCount": 3,
    }
    mock_asset_sales.return_value = {
        "grossCents": 1000,
        "platformFeeCents": 200,
        "partnerEarningsCents": 800,
        "transferredCents": 800,
        "pendingTransferCents": 0,
        "payoutCount": 2,
    }
    mock_adoption.return_value = {"publishedAssets": 4, "totalInstalls": 25}

    payload = get_publisher_revenue_analytics(MagicMock(), "partner-org")
    assert payload["earnings"]["combined"]["grossCents"] == 4000
    assert payload["adoption"]["paidSaleCount"] == 2
    assert payload["recentAssetPayouts"][0]["id"] == "payout-1"
    assert payload.get("platformTopAssets") is None

    platform_payload = get_publisher_revenue_analytics(
        MagicMock(), "partner-org", include_platform_insights=True
    )
    assert "platformTopAssets" in platform_payload
