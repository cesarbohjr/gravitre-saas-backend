"""Publisher revenue analytics (MKT-AUDIT-14.1 / STA-255)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.marketplace.payouts import get_publisher_payout_summary, list_recent_asset_payouts
from app.services.marketplace_billing_service import get_partner_earnings_summary, list_recent_usage_events


def _sum_earnings(*summaries: dict[str, Any]) -> dict[str, Any]:
    gross = sum(int(s.get("grossCents") or 0) for s in summaries)
    platform_fees = sum(int(s.get("platformFeeCents") or 0) for s in summaries)
    partner = sum(int(s.get("partnerEarningsCents") or 0) for s in summaries)
    transferred = sum(int(s.get("transferredCents") or 0) for s in summaries)
    pending = sum(int(s.get("pendingTransferCents") or 0) for s in summaries)
    return {
        "grossCents": gross,
        "platformFeeCents": platform_fees,
        "partnerEarningsCents": partner,
        "transferredCents": transferred,
        "pendingTransferCents": pending,
    }


def _aggregate_top_assets(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "assetId": "",
            "slug": None,
            "title": None,
            "grossCents": 0,
            "partnerEarningsCents": 0,
            "saleCount": 0,
        }
    )
    for row in rows:
        asset_id = str(row.get("asset_id") or "")
        if not asset_id:
            continue
        asset = row.get("marketplace_assets") or {}
        bucket = totals[asset_id]
        bucket["assetId"] = asset_id
        bucket["slug"] = asset.get("slug")
        bucket["title"] = asset.get("title")
        bucket["grossCents"] += int(row.get("gross_amount_cents") or 0)
        bucket["partnerEarningsCents"] += int(row.get("partner_earnings_cents") or 0)
        bucket["saleCount"] += 1

    ranked = sorted(totals.values(), key=lambda item: item["partnerEarningsCents"], reverse=True)
    return ranked[: max(1, min(limit, 50))]


def _publisher_asset_adoption(client: Any, org_id: str) -> dict[str, Any]:
    publisher = (
        client.table("marketplace_publishers")
        .select("id")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not publisher.data:
        return {"publishedAssets": 0, "totalInstalls": 0}

    publisher_id = publisher.data[0]["id"]
    assets = (
        client.table("marketplace_assets")
        .select("install_count")
        .eq("publisher_id", publisher_id)
        .eq("status", "published")
        .execute()
    )
    rows = assets.data or []
    return {
        "publishedAssets": len(rows),
        "totalInstalls": sum(int(row.get("install_count") or 0) for row in rows),
    }


def top_assets_by_earnings(
    client: Any,
    partner_org_id: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    rows = (
        client.table("marketplace_payouts")
        .select(
            "asset_id, gross_amount_cents, partner_earnings_cents, marketplace_assets(slug, title)"
        )
        .eq("partner_org_id", partner_org_id)
        .execute()
    )
    return _aggregate_top_assets(list(rows.data or []), limit=limit)


def platform_top_earning_assets(client: Any, *, limit: int = 10) -> list[dict[str, Any]]:
    rows = (
        client.table("marketplace_payouts")
        .select(
            "asset_id, gross_amount_cents, partner_earnings_cents, marketplace_assets(slug, title)"
        )
        .execute()
    )
    return _aggregate_top_assets(list(rows.data or []), limit=limit)


def get_publisher_revenue_analytics(
    client: Any,
    org_id: str,
    *,
    include_platform_insights: bool = False,
    recent_limit: int = 10,
    top_limit: int = 10,
) -> dict[str, Any]:
    connector_usage = get_partner_earnings_summary(client, org_id)
    asset_sales = get_publisher_payout_summary(client, org_id)
    combined = _sum_earnings(connector_usage, asset_sales)
    adoption = _publisher_asset_adoption(client, org_id)

    payload: dict[str, Any] = {
        "partnerOrgId": org_id,
        "earnings": {
            "combined": combined,
            "connectorUsage": connector_usage,
            "assetSales": asset_sales,
        },
        "adoption": {
            **adoption,
            "usageEventCount": connector_usage.get("usageEventCount", 0),
            "paidSaleCount": asset_sales.get("payoutCount", 0),
        },
        "topAssetsByEarnings": top_assets_by_earnings(client, org_id, limit=top_limit),
        "recentAssetPayouts": list_recent_asset_payouts(client, org_id, limit=recent_limit),
        "recentUsageEvents": list_recent_usage_events(client, org_id, limit=recent_limit),
    }
    if include_platform_insights:
        payload["platformTopAssets"] = platform_top_earning_assets(client, limit=top_limit)
    return payload
