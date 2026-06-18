"""Creator revenue share ledger + Stripe Connect transfers (MKT-AUDIT-12.2)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings

AUDIT_PAYOUT_RECORDED = "marketplace.payout.recorded"
AUDIT_PAYOUT_TRANSFERRED = "marketplace.payout.transferred"
RESOURCE_TYPE_MARKETPLACE_PAYOUT = "marketplace_payout"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_platform_fee_bps(settings: Settings) -> int:
    return max(0, min(10_000, int(getattr(settings, "marketplace_platform_fee_bps", 2000) or 2000)))


def _split_amounts(gross_cents: int, platform_fee_bps: int) -> tuple[int, int]:
    platform_fee = (gross_cents * platform_fee_bps) // 10_000
    partner_earnings = max(0, gross_cents - platform_fee)
    return platform_fee, partner_earnings


def _load_publisher_id(client: Any, asset_id: str) -> tuple[str | None, str | None]:
    asset = (
        client.table("marketplace_assets")
        .select("publisher_id, marketplace_publishers(org_id)")
        .eq("id", asset_id)
        .limit(1)
        .execute()
    )
    if not asset.data:
        return None, None
    row = asset.data[0]
    publisher_id = str(row["publisher_id"]) if row.get("publisher_id") else None
    publisher = row.get("marketplace_publishers") or {}
    partner_org_id = publisher.get("org_id")
    return publisher_id, str(partner_org_id) if partner_org_id else None


def record_asset_purchase_payout(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    asset_id: str,
    entitlement_id: str,
    gross_cents: int,
    currency: str,
    publisher_org_id: str | None = None,
) -> dict[str, Any] | None:
    """Write marketplace_payouts row and attempt Connect transfer."""
    del org_id  # reserved for future customer attribution
    if gross_cents <= 0:
        return None

    publisher_id, resolved_partner_org = _load_publisher_id(client, asset_id)
    if not publisher_id:
        return None

    partner_org_id = publisher_org_id or resolved_partner_org
    fee_bps = _default_platform_fee_bps(settings)
    platform_fee, partner_earnings = _split_amounts(gross_cents, fee_bps)

    row = {
        "publisher_id": publisher_id,
        "partner_org_id": partner_org_id,
        "asset_id": asset_id,
        "gross_amount_cents": gross_cents,
        "platform_fee_cents": platform_fee,
        "partner_earnings_cents": partner_earnings,
        "currency": currency.lower(),
        "status": "pending",
        "notes": f"entitlement:{entitlement_id}",
        "created_at": _now_iso(),
    }
    inserted = client.table("marketplace_payouts").insert(row).execute()
    if not inserted.data:
        return None
    payout = dict(inserted.data[0])
    _maybe_transfer_payout(client, settings, payout)
    return payout


def _get_partner_account_row(client: Any, org_id: str) -> dict[str, Any] | None:
    result = (
        client.table("marketplace_partner_accounts")
        .select("*")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def _maybe_transfer_payout(client: Any, settings: Settings, payout: dict[str, Any]) -> None:
    partner_org_id = payout.get("partner_org_id")
    earnings = int(payout.get("partner_earnings_cents") or 0)
    if not partner_org_id or earnings <= 0:
        client.table("marketplace_payouts").update({"status": "cancelled"}).eq("id", payout["id"]).execute()
        return

    account = _get_partner_account_row(client, str(partner_org_id))
    if not account or account.get("connect_status") != "active" or not account.get("stripe_connect_account_id"):
        return

    if not (settings.stripe_secret_key or "").strip():
        return

    from app.billing.stripe_connect import create_connect_transfer

    try:
        transfer = create_connect_transfer(
            settings,
            amount_cents=earnings,
            currency=str(payout.get("currency") or "usd"),
            destination_account_id=str(account["stripe_connect_account_id"]),
            metadata={
                "payout_id": str(payout.get("id")),
                "asset_id": str(payout.get("asset_id") or ""),
                "partner_org_id": str(partner_org_id),
            },
        )
        client.table("marketplace_payouts").update(
            {
                "status": "transferred",
                "stripe_transfer_id": transfer.id,
            }
        ).eq("id", payout["id"]).execute()
    except Exception:
        client.table("marketplace_payouts").update({"status": "failed"}).eq("id", payout["id"]).execute()


def sync_pending_payouts(client: Any, settings: Settings, *, partner_org_id: str) -> dict[str, Any]:
    """Retry pending payouts for a publisher org."""
    pending = (
        client.table("marketplace_payouts")
        .select("*")
        .eq("partner_org_id", partner_org_id)
        .eq("status", "pending")
        .execute()
    )
    transferred = 0
    failed = 0
    for row in pending.data or []:
        before = row.get("status")
        _maybe_transfer_payout(client, settings, dict(row))
        after = (
            client.table("marketplace_payouts")
            .select("status")
            .eq("id", row["id"])
            .limit(1)
            .execute()
        )
        status_value = (after.data or [{}])[0].get("status")
        if status_value == "transferred" and before != "transferred":
            transferred += 1
        elif status_value == "failed":
            failed += 1
    return {"transferred": transferred, "failed": failed, "pendingReviewed": len(pending.data or [])}


def get_publisher_payout_summary(client: Any, partner_org_id: str) -> dict[str, Any]:
    rows = (
        client.table("marketplace_payouts")
        .select("gross_amount_cents, platform_fee_cents, partner_earnings_cents, status")
        .eq("partner_org_id", partner_org_id)
        .execute()
    )
    data = rows.data or []
    gross = sum(int(r.get("gross_amount_cents") or 0) for r in data)
    platform_fees = sum(int(r.get("platform_fee_cents") or 0) for r in data)
    earnings = sum(int(r.get("partner_earnings_cents") or 0) for r in data)
    transferred = sum(
        int(r.get("partner_earnings_cents") or 0)
        for r in data
        if r.get("status") == "transferred"
    )
    return {
        "grossCents": gross,
        "platformFeeCents": platform_fees,
        "partnerEarningsCents": earnings,
        "transferredCents": transferred,
        "pendingTransferCents": max(0, earnings - transferred),
        "payoutCount": len(data),
    }
