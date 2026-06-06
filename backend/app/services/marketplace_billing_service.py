"""Marketplace v2 billing — Connect onboarding, pricing, usage ledger (STA-96)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import Settings
from app.core.errors import error_detail

RESOURCE_TYPE_MARKETPLACE_BILLING = "marketplace_billing"
AUDIT_CONNECT_ONBOARDING = "marketplace.billing.connect_onboarding"
AUDIT_PRICING_UPDATED = "marketplace.billing.pricing_updated"
AUDIT_USAGE_RECORDED = "marketplace.billing.usage_recorded"
AUDIT_INSTALL_RECORDED = "marketplace.billing.install_recorded"

PRICING_MODELS = frozenset({"free", "flat_monthly", "per_invocation"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_platform_fee_bps(settings: Settings) -> int:
    return max(0, min(10_000, int(getattr(settings, "marketplace_platform_fee_bps", 2000) or 2000)))


def _normalize_partner_account(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {
            "connected": False,
            "connectStatus": "pending",
            "chargesEnabled": False,
            "payoutsEnabled": False,
            "detailsSubmitted": False,
            "stripeConnectAccountId": None,
            "onboardingCompletedAt": None,
        }
    return {
        "connected": bool(row.get("stripe_connect_account_id")),
        "connectStatus": row.get("connect_status") or "pending",
        "chargesEnabled": bool(row.get("charges_enabled")),
        "payoutsEnabled": bool(row.get("payouts_enabled")),
        "detailsSubmitted": bool(row.get("details_submitted")),
        "stripeConnectAccountId": row.get("stripe_connect_account_id"),
        "onboardingCompletedAt": row.get("onboarding_completed_at"),
    }


def _normalize_pricing(row: dict[str, Any], *, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "registryId": str(row["registry_id"]),
        "partnerOrgId": str(row["partner_org_id"]),
        "pricingModel": row.get("pricing_model") or "free",
        "priceCents": int(row.get("price_cents") or 0),
        "currency": (row.get("currency") or "usd").lower(),
        "platformFeeBps": int(row.get("platform_fee_bps") or 0),
        "stripePriceId": row.get("stripe_price_id"),
        "active": bool(row.get("active", True)),
        "vendor": registry.get("vendor") if registry else None,
        "connectorName": registry.get("name") if registry else None,
        "updatedAt": row.get("updated_at"),
    }


def _get_partner_account_row(client: Any, org_id: str) -> dict[str, Any] | None:
    result = (
        client.table("marketplace_partner_accounts")
        .select("*")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def _load_org_name(client: Any, org_id: str) -> str:
    row = client.table("organizations").select("name").eq("id", org_id).limit(1).execute()
    if not row.data:
        return "Partner"
    return str(row.data[0].get("name") or "Partner")


def _require_stripe(settings: Settings) -> None:
    if not (settings.stripe_secret_key or "").strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Stripe is not configured", "STRIPE_NOT_CONFIGURED"),
        )


def get_partner_billing_status(client: Any, org_id: str) -> dict[str, Any]:
    account = _normalize_partner_account(_get_partner_account_row(client, org_id))
    pricing = list_partner_pricing(client, org_id)
    earnings = get_partner_earnings_summary(client, org_id)
    return {
        "partnerOrgId": org_id,
        "account": account,
        "pricingCount": len(pricing),
        "earnings": earnings,
        "platformFeeBps": None,
    }


def ensure_partner_connect_account(client: Any, settings: Settings, *, org_id: str) -> dict[str, Any]:
    """Create Stripe Connect account row if missing."""
    _require_stripe(settings)
    existing = _get_partner_account_row(client, org_id)
    if existing and existing.get("stripe_connect_account_id"):
        return _normalize_partner_account(existing)

    from app.billing.stripe_connect import create_express_connect_account

    org_name = _load_org_name(client, org_id)
    account = create_express_connect_account(settings, org_id=org_id, org_name=org_name)
    row = {
        "org_id": org_id,
        "stripe_connect_account_id": account.id,
        "connect_status": "onboarding",
        "charges_enabled": bool(getattr(account, "charges_enabled", False)),
        "payouts_enabled": bool(getattr(account, "payouts_enabled", False)),
        "details_submitted": bool(getattr(account, "details_submitted", False)),
        "updated_at": _now_iso(),
    }
    upserted = client.table("marketplace_partner_accounts").upsert(row, on_conflict="org_id").execute()
    if not upserted.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Connect account create failed")
    return _normalize_partner_account(upserted.data[0])


def create_partner_onboarding_link(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    return_url: str,
    refresh_url: str,
) -> dict[str, Any]:
    account = ensure_partner_connect_account(client, settings, org_id=org_id)
    account_id = account.get("stripeConnectAccountId")
    if not account_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Connect account missing")

    from app.billing.stripe_connect import create_connect_onboarding_link

    link = create_connect_onboarding_link(
        settings,
        account_id=account_id,
        return_url=return_url,
        refresh_url=refresh_url,
    )
    client.table("marketplace_partner_accounts").update(
        {"connect_status": "onboarding", "updated_at": _now_iso()}
    ).eq("org_id", org_id).execute()
    return {"url": link.url, "expiresAt": getattr(link, "expires_at", None)}


def sync_partner_connect_account(client: Any, settings: Settings, *, org_id: str) -> dict[str, Any]:
    row = _get_partner_account_row(client, org_id)
    if not row or not row.get("stripe_connect_account_id"):
        return _normalize_partner_account(row)

    from app.billing.stripe_connect import retrieve_connect_account

    _require_stripe(settings)
    account = retrieve_connect_account(settings, str(row["stripe_connect_account_id"]))
    charges_enabled = bool(getattr(account, "charges_enabled", False))
    payouts_enabled = bool(getattr(account, "payouts_enabled", False))
    details_submitted = bool(getattr(account, "details_submitted", False))
    connect_status = "onboarding"
    if charges_enabled and payouts_enabled and details_submitted:
        connect_status = "active"
    elif details_submitted:
        connect_status = "restricted"

    update = {
        "charges_enabled": charges_enabled,
        "payouts_enabled": payouts_enabled,
        "details_submitted": details_submitted,
        "connect_status": connect_status,
        "updated_at": _now_iso(),
    }
    if connect_status == "active" and not row.get("onboarding_completed_at"):
        update["onboarding_completed_at"] = _now_iso()

    updated = (
        client.table("marketplace_partner_accounts")
        .update(update)
        .eq("org_id", org_id)
        .execute()
    )
    data = updated.data[0] if updated.data else {**row, **update}
    return _normalize_partner_account(data)


def _get_registry_for_partner(client: Any, registry_id: str, partner_org_id: str) -> dict[str, Any]:
    result = (
        client.table("partner_connector_registry")
        .select("*")
        .eq("id", registry_id)
        .eq("org_id", partner_org_id)
        .eq("status", "published")
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_detail("Published connector not found for this org", "REGISTRY_NOT_FOUND"),
        )
    return result.data[0]


def upsert_connector_pricing(
    client: Any,
    settings: Settings,
    *,
    partner_org_id: str,
    registry_id: str,
    pricing_model: str,
    price_cents: int,
    currency: str = "usd",
) -> dict[str, Any]:
    model = (pricing_model or "free").strip().lower()
    if model not in PRICING_MODELS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid pricing model")
    if model == "free":
        price_cents = 0
    elif price_cents <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("priceCents must be > 0 for paid models", "INVALID_PRICE"),
        )

    registry = _get_registry_for_partner(client, registry_id, partner_org_id)
    account = _get_partner_account_row(client, partner_org_id)
    if model != "free":
        if not account or account.get("connect_status") != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_detail(
                    "Complete Stripe Connect onboarding before setting paid pricing",
                    "CONNECT_ONBOARDING_REQUIRED",
                ),
            )

    fee_bps = _default_platform_fee_bps(settings)
    row = {
        "registry_id": registry_id,
        "partner_org_id": partner_org_id,
        "pricing_model": model,
        "price_cents": price_cents,
        "currency": (currency or "usd").lower(),
        "platform_fee_bps": fee_bps,
        "active": True,
        "updated_at": _now_iso(),
    }
    upserted = (
        client.table("marketplace_connector_pricing")
        .upsert(row, on_conflict="registry_id")
        .execute()
    )
    if not upserted.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Pricing upsert failed")
    return _normalize_pricing(upserted.data[0], registry=registry)


def list_partner_pricing(client: Any, partner_org_id: str) -> list[dict[str, Any]]:
    registry_rows = (
        client.table("partner_connector_registry")
        .select("*")
        .eq("org_id", partner_org_id)
        .eq("status", "published")
        .execute()
    )
    registry_by_id = {str(row["id"]): row for row in (registry_rows.data or [])}
    if not registry_by_id:
        return []

    pricing_result = (
        client.table("marketplace_connector_pricing")
        .select("*")
        .eq("partner_org_id", partner_org_id)
        .execute()
    )
    pricing_by_registry = {str(row["registry_id"]): row for row in (pricing_result.data or [])}

    items: list[dict[str, Any]] = []
    for registry_id, registry in registry_by_id.items():
        pricing_row = pricing_by_registry.get(registry_id)
        if pricing_row:
            items.append(_normalize_pricing(pricing_row, registry=registry))
        else:
            items.append(
                {
                    "id": None,
                    "registryId": registry_id,
                    "partnerOrgId": partner_org_id,
                    "pricingModel": "free",
                    "priceCents": 0,
                    "currency": "usd",
                    "platformFeeBps": _default_platform_fee_bps_from_client(),
                    "stripePriceId": None,
                    "active": True,
                    "vendor": registry.get("vendor"),
                    "connectorName": registry.get("name"),
                    "updatedAt": None,
                }
            )
    return items


def _default_platform_fee_bps_from_client() -> int:
    return 2000


def get_pricing_for_vendor(client: Any, vendor: str) -> dict[str, Any] | None:
    slug = (vendor or "").strip().lower()
    if not slug:
        return None
    registry = (
        client.table("partner_connector_registry")
        .select("id, org_id, vendor, name")
        .eq("vendor", slug)
        .eq("status", "published")
        .limit(1)
        .execute()
    )
    if not registry.data:
        return None
    reg = registry.data[0]
    pricing = (
        client.table("marketplace_connector_pricing")
        .select("*")
        .eq("registry_id", reg["id"])
        .eq("active", True)
        .limit(1)
        .execute()
    )
    if not pricing.data:
        return {
            "registryId": str(reg["id"]),
            "partnerOrgId": str(reg["org_id"]),
            "vendor": reg.get("vendor"),
            "connectorName": reg.get("name"),
            "pricingModel": "free",
            "priceCents": 0,
            "currency": "usd",
            "platformFeeBps": 2000,
        }
    return _normalize_pricing(pricing.data[0], registry=reg)


def enrich_registry_with_pricing(client: Any, connectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not connectors:
        return connectors
    registry_ids = [c["id"] for c in connectors if c.get("id")]
    pricing_result = (
        client.table("marketplace_connector_pricing")
        .select("*")
        .in_("registry_id", registry_ids)
        .eq("active", True)
        .execute()
    )
    pricing_by_registry = {str(row["registry_id"]): row for row in (pricing_result.data or [])}
    enriched: list[dict[str, Any]] = []
    for connector in connectors:
        row = dict(connector)
        pricing_row = pricing_by_registry.get(str(connector.get("id")))
        if pricing_row:
            row["pricing"] = {
                "model": pricing_row.get("pricing_model") or "free",
                "priceCents": int(pricing_row.get("price_cents") or 0),
                "currency": pricing_row.get("currency") or "usd",
            }
        else:
            row["pricing"] = {"model": "free", "priceCents": 0, "currency": "usd"}
        enriched.append(row)
    return enriched


def record_marketplace_install(
    client: Any,
    *,
    customer_org_id: str,
    connector_id: str,
    vendor: str,
) -> dict[str, Any] | None:
    pricing = get_pricing_for_vendor(client, vendor)
    if not pricing:
        return None
    row = {
        "registry_id": pricing["registryId"],
        "partner_org_id": pricing["partnerOrgId"],
        "customer_org_id": customer_org_id,
        "connector_id": connector_id,
        "status": "active",
        "updated_at": _now_iso(),
    }
    result = client.table("marketplace_connector_installs").upsert(row, on_conflict="registry_id,customer_org_id").execute()
    return result.data[0] if result.data else None


def _split_amounts(gross_cents: int, platform_fee_bps: int) -> tuple[int, int]:
    platform_fee = (gross_cents * platform_fee_bps) // 10_000
    partner_earnings = max(0, gross_cents - platform_fee)
    return platform_fee, partner_earnings


def record_marketplace_usage_for_invoke(
    client: Any,
    settings: Settings,
    *,
    customer_org_id: str,
    connector_id: str | None,
    vendor: str,
    action: str,
    idempotency_key: str,
) -> dict[str, Any] | None:
    pricing = get_pricing_for_vendor(client, vendor)
    if not pricing or pricing.get("pricingModel") != "per_invocation":
        return None
    unit_price = int(pricing.get("priceCents") or 0)
    if unit_price <= 0:
        return None

    gross = unit_price
    fee_bps = int(pricing.get("platformFeeBps") or _default_platform_fee_bps(settings))
    platform_fee, partner_earnings = _split_amounts(gross, fee_bps)

    row = {
        "registry_id": pricing["registryId"],
        "partner_org_id": pricing["partnerOrgId"],
        "customer_org_id": customer_org_id,
        "connector_id": connector_id,
        "action": action,
        "quantity": 1,
        "unit_price_cents": unit_price,
        "gross_amount_cents": gross,
        "platform_fee_cents": platform_fee,
        "partner_earnings_cents": partner_earnings,
        "currency": pricing.get("currency") or "usd",
        "idempotency_key": idempotency_key,
        "transfer_status": "pending",
    }
    try:
        inserted = client.table("marketplace_usage_events").insert(row).execute()
    except Exception as exc:  # noqa: BLE001
        if "duplicate" in str(exc).lower() or "23505" in str(exc):
            return None
        raise
    if not inserted.data:
        return None

    usage = inserted.data[0]
    _maybe_transfer_partner_earnings(client, settings, usage)
    return usage


def _maybe_transfer_partner_earnings(client: Any, settings: Settings, usage: dict[str, Any]) -> None:
    partner_org_id = str(usage.get("partner_org_id"))
    earnings = int(usage.get("partner_earnings_cents") or 0)
    if earnings <= 0:
        client.table("marketplace_usage_events").update({"transfer_status": "skipped"}).eq(
            "id", usage["id"]
        ).execute()
        return

    account = _get_partner_account_row(client, partner_org_id)
    if not account or account.get("connect_status") != "active" or not account.get("stripe_connect_account_id"):
        return

    if not (settings.stripe_secret_key or "").strip():
        return

    from app.billing.stripe_connect import create_connect_transfer

    try:
        transfer = create_connect_transfer(
            settings,
            amount_cents=earnings,
            currency=str(usage.get("currency") or "usd"),
            destination_account_id=str(account["stripe_connect_account_id"]),
            metadata={
                "usage_event_id": str(usage.get("id")),
                "partner_org_id": partner_org_id,
                "action": str(usage.get("action") or ""),
            },
        )
        client.table("marketplace_usage_events").update(
            {"transfer_status": "transferred", "stripe_transfer_id": transfer.id}
        ).eq("id", usage["id"]).execute()
    except Exception:
        client.table("marketplace_usage_events").update({"transfer_status": "failed"}).eq(
            "id", usage["id"]
        ).execute()


def build_invoke_idempotency_key(ctx: Any, action: str, connector_id: str | None) -> str:
    raw = f"{ctx.org_id}:{connector_id or ''}:{action}:{ctx.run_id or ''}:{ctx.agent_id or ''}:{uuid4().hex}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_partner_earnings_summary(client: Any, partner_org_id: str) -> dict[str, Any]:
    events = (
        client.table("marketplace_usage_events")
        .select("gross_amount_cents, platform_fee_cents, partner_earnings_cents, transfer_status")
        .eq("partner_org_id", partner_org_id)
        .execute()
    )
    rows = events.data or []
    gross = sum(int(r.get("gross_amount_cents") or 0) for r in rows)
    platform_fees = sum(int(r.get("platform_fee_cents") or 0) for r in rows)
    partner_total = sum(int(r.get("partner_earnings_cents") or 0) for r in rows)
    transferred = sum(
        int(r.get("partner_earnings_cents") or 0)
        for r in rows
        if r.get("transfer_status") == "transferred"
    )
    pending = partner_total - transferred
    installs = (
        client.table("marketplace_connector_installs")
        .select("id", count="exact")
        .eq("partner_org_id", partner_org_id)
        .eq("status", "active")
        .execute()
    )
    install_count = installs.count if getattr(installs, "count", None) is not None else len(installs.data or [])
    return {
        "grossCents": gross,
        "platformFeeCents": platform_fees,
        "partnerEarningsCents": partner_total,
        "transferredCents": transferred,
        "pendingTransferCents": max(0, pending),
        "usageEventCount": len(rows),
        "activeInstallCount": install_count,
    }


def list_recent_usage_events(client: Any, partner_org_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    result = (
        client.table("marketplace_usage_events")
        .select("id, action, gross_amount_cents, partner_earnings_cents, transfer_status, created_at, customer_org_id")
        .eq("partner_org_id", partner_org_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [
        {
            "id": str(row["id"]),
            "action": row.get("action"),
            "grossCents": int(row.get("gross_amount_cents") or 0),
            "partnerEarningsCents": int(row.get("partner_earnings_cents") or 0),
            "transferStatus": row.get("transfer_status"),
            "customerOrgId": str(row.get("customer_org_id")),
            "createdAt": row.get("created_at"),
        }
        for row in (result.data or [])
    ]


def handle_connect_account_updated(client: Any, settings: Settings, account: dict[str, Any]) -> None:
    metadata = account.get("metadata") or {}
    org_id = metadata.get("org_id")
    if not org_id:
        return
    sync_partner_connect_account(client, settings, org_id=str(org_id))
