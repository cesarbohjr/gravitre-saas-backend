"""Wholesale billing for MSP partners.

How the money works: the MSP holds ONE Stripe subscription whose items are the
wholesale Prices (one per plan tier) with quantity = active clients on that
tier. The MSP bills its own clients whatever it likes; Gravitre never charges
the client. Each client's entitlement comes from its ``msp_clients.plan_code``
while the MSP subscription is active or trialing, written to the client's
``org_billing`` row with ``billing_source='msp'`` so the existing entitlement
and billing-gate code keeps working unchanged.

This module never touches the MSP's own ``org_billing`` row: an MSP can keep
its own Gravitre plan for its own workspace alongside the wholesale account.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import stripe

from app.config import Settings
from app.core.logging import get_logger
from app.core.org_state_cache import invalidate_org_state

logger = get_logger(__name__)

WHOLESALE_KIND = "msp_wholesale"
MSP_TIERS: tuple[str, ...] = ("node", "control", "command")
# Grace given to a client workspace when it is not (or no longer) covered by an
# active MSP subscription, so its people are never locked out without warning.
CLIENT_GRACE_DAYS = 7

_PRICE_CACHE: dict[str, tuple[float, dict[str, Any] | None]] = {}
_PRICE_CACHE_TTL_SECONDS = 600


class WholesaleBillingError(Exception):
    """A clear, user-facing reason wholesale billing cannot proceed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _now() -> datetime:
    return datetime.now(timezone.utc)


def wholesale_price_ids(settings: Settings) -> dict[str, str]:
    return {
        tier: str(getattr(settings, f"stripe_price_id_msp_{tier}_wholesale", "") or "").strip()
        for tier in MSP_TIERS
    }


def tier_for_wholesale_price(settings: Settings, price_id: str | None) -> str | None:
    if not price_id:
        return None
    for tier, configured in wholesale_price_ids(settings).items():
        if configured and configured == price_id:
            return tier
    return None


def wholesale_setup(settings: Settings) -> dict[str, Any]:
    """Whether wholesale billing can run, per tier, without calling Stripe."""
    prices = wholesale_price_ids(settings)
    has_stripe = bool(str(getattr(settings, "stripe_secret_key", "") or "").strip())
    configured_tiers = [tier for tier, pid in prices.items() if pid]
    if not has_stripe or not configured_tiers:
        status = "not_configured"
    elif len(configured_tiers) < len(MSP_TIERS):
        status = "partial"
    else:
        status = "ready"
    return {
        "status": status,
        "stripe_configured": has_stripe,
        "configured_tiers": configured_tiers,
        "message": (
            "Wholesale billing isn't set up yet. You can add clients now; "
            "Gravitre will ask you to start billing once it is."
            if status == "not_configured"
            else None
        ),
    }


def wholesale_price_info(settings: Settings, tier: str) -> dict[str, Any] | None:
    """Unit amount (cents), currency and interval of a tier's wholesale Price.

    Read from Stripe and cached briefly. None when not configured or unreadable,
    so callers show "not available" rather than inventing a number.
    """
    price_id = wholesale_price_ids(settings).get(tier) or ""
    if not price_id or not getattr(settings, "stripe_secret_key", ""):
        return None
    cached = _PRICE_CACHE.get(price_id)
    if cached and time.monotonic() - cached[0] < _PRICE_CACHE_TTL_SECONDS:
        return cached[1]
    info: dict[str, Any] | None = None
    try:
        stripe.api_key = settings.stripe_secret_key
        price = stripe.Price.retrieve(price_id)
        recurring = price.get("recurring") or {}
        amount = price.get("unit_amount")
        if amount is not None:
            interval = str(recurring.get("interval") or "month")
            count = int(recurring.get("interval_count") or 1)
            info = {
                "price_id": price_id,
                "unit_amount_cents": int(amount),
                "currency": str(price.get("currency") or "usd"),
                "interval": interval,
                "interval_count": count,
                "monthly_cents": monthly_cents(int(amount), interval, count),
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("msp_wholesale_price_lookup_failed tier=%s error=%s", tier, type(exc).__name__)
        info = None
    _PRICE_CACHE[price_id] = (time.monotonic(), info)
    return info


def monthly_cents(amount_cents: int, interval: str, interval_count: int = 1) -> int:
    count = max(1, int(interval_count or 1))
    if interval == "year":
        return round(amount_cents / (12 * count))
    if interval == "week":
        return round(amount_cents * 52 / (12 * count))
    if interval == "day":
        return round(amount_cents * 365 / (12 * count))
    return round(amount_cents / count)


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def get_billing_account(client: Any, msp_org_id: str) -> dict[str, Any] | None:
    rows = (
        client.table("msp_billing_accounts").select("*").eq("msp_org_id", msp_org_id).limit(1).execute().data
        or []
    )
    return dict(rows[0]) if rows else None


def _upsert_billing_account(client: Any, msp_org_id: str, payload: dict[str, Any]) -> None:
    client.table("msp_billing_accounts").upsert(
        {"msp_org_id": msp_org_id, **payload, "updated_at": _now().isoformat()},
        on_conflict="msp_org_id",
    ).execute()


def active_client_rows(client: Any, msp_org_id: str) -> list[dict[str, Any]]:
    return (
        client.table("msp_clients")
        .select("id,client_org_id,plan_code,status")
        .eq("msp_org_id", msp_org_id)
        .eq("status", "active")
        .execute()
        .data
        or []
    )


def desired_quantities(client: Any, msp_org_id: str) -> dict[str, int]:
    counts = {tier: 0 for tier in MSP_TIERS}
    for row in active_client_rows(client, msp_org_id):
        tier = str(row.get("plan_code") or "")
        if tier in counts:
            counts[tier] += 1
    return counts


def subscription_covers_clients(account: dict[str, Any] | None) -> bool:
    return bool(account) and str(account.get("status") or "") in {"active", "trialing"}


# ---------------------------------------------------------------------------
# Client entitlement mirroring
# ---------------------------------------------------------------------------


def _client_status_for(account: dict[str, Any] | None) -> tuple[str, str | None]:
    """(billing_status, current_period_end) for a client covered by this MSP."""
    status = str((account or {}).get("status") or "none")
    period_end = (account or {}).get("current_period_end")
    if status in {"active", "trialing"}:
        return status, period_end
    if status == "past_due":
        return "past_due", period_end
    if status == "canceled":
        return "cancelled", period_end
    # none / incomplete: the MSP hasn't started paying yet. Normal trial.
    return "trialing", (_now() + timedelta(days=CLIENT_GRACE_DAYS)).isoformat()


def write_client_entitlement(
    client: Any,
    *,
    msp_org_id: str,
    client_org_id: str,
    plan_code: str,
    account: dict[str, Any] | None,
) -> None:
    existing = (
        client.table("org_billing")
        .select("org_id,billing_status,current_period_end,billing_source")
        .eq("org_id", client_org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    billing_status, period_end = _client_status_for(account)
    if (
        billing_status == "trialing"
        and existing
        and existing[0].get("billing_source") == "msp"
        and existing[0].get("billing_status") == "trialing"
        and existing[0].get("current_period_end")
    ):
        # Keep the original grace end; re-syncs must not extend a trial forever.
        period_end = existing[0]["current_period_end"]
    client.table("org_billing").upsert(
        {
            "org_id": client_org_id,
            "plan_code": plan_code,
            "billing_status": billing_status,
            "current_period_end": period_end,
            "billing_source": "msp",
            "billed_by_org_id": msp_org_id,
            "cancel_at_period_end": False,
            "updated_at": _now().isoformat(),
        },
        on_conflict="org_id",
    ).execute()
    invalidate_org_state(client_org_id)


def release_client_entitlement(client: Any, *, client_org_id: str, msp_org_id: str) -> None:
    """Client leaves MSP billing: back to self billing with a short grace trial."""
    rows = (
        client.table("org_billing")
        .select("org_id,billed_by_org_id")
        .eq("org_id", client_org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if rows and str(rows[0].get("billed_by_org_id") or "") not in {"", msp_org_id}:
        return  # billed by someone else now; never touch it
    client.table("org_billing").upsert(
        {
            "org_id": client_org_id,
            "billing_source": "self",
            "billed_by_org_id": None,
            "billing_status": "trialing",
            "current_period_end": (_now() + timedelta(days=CLIENT_GRACE_DAYS)).isoformat(),
            "stripe_subscription_id": None,
            "stripe_price_id": None,
            "updated_at": _now().isoformat(),
        },
        on_conflict="org_id",
    ).execute()
    invalidate_org_state(client_org_id)


def propagate_to_clients(client: Any, msp_org_id: str) -> int:
    """Mirror the MSP subscription status onto every active client."""
    account = get_billing_account(client, msp_org_id)
    rows = active_client_rows(client, msp_org_id)
    for row in rows:
        write_client_entitlement(
            client,
            msp_org_id=msp_org_id,
            client_org_id=str(row["client_org_id"]),
            plan_code=str(row["plan_code"]),
            account=account,
        )
    return len(rows)


def own_subscription_conflict(client: Any, client_org_id: str) -> str | None:
    """Reason a workspace can't move to MSP billing, or None.

    Never double-bill: a workspace still paying Gravitre directly must cancel
    that subscription (and let it end) first.
    """
    rows = (
        client.table("org_billing")
        .select("billing_status,stripe_subscription_id,billing_source")
        .eq("org_id", client_org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return None
    row = rows[0]
    if row.get("billing_source") == "msp":
        return None
    status = str(row.get("billing_status") or "").lower()
    if row.get("stripe_subscription_id") and status in {"active", "trialing", "past_due", "pending", "unpaid"}:
        return (
            "This workspace still pays Gravitre directly. Its owner needs to cancel that "
            "subscription in Settings › Billing and let it end before it can be billed "
            "through a partner, so nobody is charged twice."
        )
    return None


# ---------------------------------------------------------------------------
# Stripe: quantity sync and first checkout
# ---------------------------------------------------------------------------


def sync_wholesale_quantities(client: Any, settings: Settings, msp_org_id: str) -> dict[str, Any]:
    """Set each wholesale item's quantity to the number of active clients.

    Absolute quantities make this safe to retry. Stripe prorates changes.
    Returns a status the UI can explain: synced / checkout_required /
    not_configured / no_change / error.
    """
    quantities = desired_quantities(client, msp_org_id)
    setup = wholesale_setup(settings)
    account = get_billing_account(client, msp_org_id)
    sub_id = str((account or {}).get("stripe_subscription_id") or "").strip()
    if setup["status"] == "not_configured":
        return {"status": "not_configured", "quantities": quantities}
    if not sub_id or str((account or {}).get("status")) == "canceled":
        needed = any(quantities.values())
        return {"status": "checkout_required" if needed else "no_change", "quantities": quantities}

    prices = wholesale_price_ids(settings)
    missing = [tier for tier, qty in quantities.items() if qty and not prices.get(tier)]
    if missing:
        return {
            "status": "error",
            "quantities": quantities,
            "message": f"Wholesale price for {', '.join(missing)} isn't set up yet.",
        }
    try:
        stripe.api_key = settings.stripe_secret_key
        subscription = stripe.Subscription.retrieve(sub_id)
        items_by_price: dict[str, dict[str, Any]] = {}
        for item in ((subscription.get("items") or {}).get("data") or []):
            price = item.get("price") or {}
            pid = price.get("id") if isinstance(price, dict) else str(price or "")
            if pid:
                items_by_price[str(pid)] = item
        updates: list[dict[str, Any]] = []
        for tier, qty in quantities.items():
            pid = prices.get(tier)
            if not pid:
                continue
            item = items_by_price.get(pid)
            if item is not None:
                if int(item.get("quantity") or 0) != qty:
                    updates.append({"id": item["id"], "quantity": qty})
            elif qty > 0:
                updates.append({"price": pid, "quantity": qty})
        if updates:
            stripe.Subscription.modify(
                sub_id,
                items=updates,
                proration_behavior="create_prorations",
                metadata={"gravitre_kind": WHOLESALE_KIND, "msp_org_id": msp_org_id},
            )
        _upsert_billing_account(
            client,
            msp_org_id,
            {"last_synced_quantities": quantities, "last_synced_at": _now().isoformat()},
        )
        return {"status": "synced" if updates else "no_change", "quantities": quantities}
    except stripe.error.StripeError as exc:
        logger.warning("msp_wholesale_sync_failed msp_org_id=%s error=%s", msp_org_id, type(exc).__name__)
        return {
            "status": "error",
            "quantities": quantities,
            "message": "Stripe couldn't update your wholesale subscription. Try again in a minute.",
        }


def create_wholesale_checkout(
    client: Any, settings: Settings, *, msp_org_id: str, user_id: str
) -> str:
    """Stripe Checkout URL that starts the MSP's wholesale subscription."""
    setup = wholesale_setup(settings)
    if setup["status"] == "not_configured":
        raise WholesaleBillingError("not_configured", setup["message"])
    account = get_billing_account(client, msp_org_id)
    if account and account.get("stripe_subscription_id") and account.get("status") not in {"canceled", "none"}:
        raise WholesaleBillingError("already_active", "Wholesale billing is already running for this account.")
    quantities = desired_quantities(client, msp_org_id)
    prices = wholesale_price_ids(settings)
    line_items = [
        {"price": prices[tier], "quantity": qty}
        for tier, qty in quantities.items()
        if qty > 0 and prices.get(tier)
    ]
    if not line_items:
        raise WholesaleBillingError("no_clients", "Add a client first. Billing starts with your first active client.")
    missing = [tier for tier, qty in quantities.items() if qty and not prices.get(tier)]
    if missing:
        raise WholesaleBillingError("not_configured", f"Wholesale price for {', '.join(missing)} isn't set up yet.")

    stripe.api_key = settings.stripe_secret_key
    customer_id = str((account or {}).get("stripe_customer_id") or "").strip()
    if not customer_id:
        customer = stripe.Customer.create(
            metadata={"msp_org_id": msp_org_id, "gravitre_kind": WHOLESALE_KIND, "created_by": user_id}
        )
        customer_id = str(customer["id"])
        _upsert_billing_account(client, msp_org_id, {"stripe_customer_id": customer_id, "status": "none"})
    app_url = (settings.public_app_url or "http://localhost:3000").rstrip("/")
    metadata = {"gravitre_kind": WHOLESALE_KIND, "msp_org_id": msp_org_id, "user_id": user_id}
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=line_items,
        success_url=f"{app_url}/settings/clients?billing=started",
        cancel_url=f"{app_url}/settings/clients?billing=cancelled",
        metadata=metadata,
        subscription_data={"metadata": metadata},
    )
    return str(session.url)


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

_STATUS_MAP = {
    "active": "active",
    "trialing": "trialing",
    "past_due": "past_due",
    "unpaid": "past_due",
    "canceled": "canceled",
    "cancelled": "canceled",
    "incomplete": "incomplete",
    "incomplete_expired": "canceled",
    "paused": "past_due",
}


def _iso(ts: Any) -> str | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def is_wholesale_event(client: Any, event_type: str, data: dict[str, Any], metadata: dict[str, Any]) -> bool:
    if str((metadata or {}).get("gravitre_kind") or "") == WHOLESALE_KIND:
        return True
    if event_type.startswith("customer.subscription.") and data.get("id"):
        try:
            rows = (
                client.table("msp_billing_accounts")
                .select("msp_org_id")
                .eq("stripe_subscription_id", str(data["id"]))
                .limit(1)
                .execute()
                .data
                or []
            )
            return bool(rows)
        except Exception:  # noqa: BLE001 - table missing before migration
            return False
    return False


def _msp_org_for(client: Any, data: dict[str, Any], metadata: dict[str, Any]) -> str | None:
    """Resolve the MSP from our own records; metadata must agree when present."""
    sub_id = str(data.get("subscription") or data.get("id") or "")
    customer_id = str(data.get("customer") or "")
    claimed = str((metadata or {}).get("msp_org_id") or "").strip() or None
    for column, value in (("stripe_subscription_id", sub_id), ("stripe_customer_id", customer_id)):
        if not value:
            continue
        rows = (
            client.table("msp_billing_accounts").select("msp_org_id").eq(column, value).limit(1).execute().data
            or []
        )
        if rows:
            owner = str(rows[0]["msp_org_id"])
            if claimed and claimed != owner:
                raise ValueError("Wholesale event MSP does not match Stripe customer owner")
            return owner
    return None


def apply_wholesale_event(
    client: Any, settings: Settings, event_type: str, data: dict[str, Any], metadata: dict[str, Any]
) -> str | None:
    """Record the MSP subscription state and mirror it to every active client."""
    msp_org_id = _msp_org_for(client, data, metadata)
    if not msp_org_id:
        logger.warning("msp_wholesale_event_unmatched type=%s", event_type)
        return None
    if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        sub_id = str(data.get("subscription") or "").strip()
        if not sub_id:
            return msp_org_id
        stripe.api_key = settings.stripe_secret_key
        live = stripe.Subscription.retrieve(sub_id)
        live_customer = live.get("customer")
        if isinstance(live_customer, dict):
            live_customer = live_customer.get("id")
        if str(live_customer or "") != str(data.get("customer") or ""):
            raise ValueError("Stripe checkout customer does not match wholesale subscription")
        _upsert_billing_account(
            client,
            msp_org_id,
            {
                "stripe_customer_id": str(data.get("customer") or ""),
                "stripe_subscription_id": sub_id,
                "status": _STATUS_MAP.get(str(live.get("status") or "").lower(), "incomplete"),
                "current_period_end": _iso(live.get("current_period_end")),
                "cancel_at_period_end": bool(live.get("cancel_at_period_end") or False),
            },
        )
    elif event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        _upsert_billing_account(
            client,
            msp_org_id,
            {
                "stripe_customer_id": str(data.get("customer") or ""),
                "stripe_subscription_id": str(data.get("id") or ""),
                "status": _STATUS_MAP.get(str(data.get("status") or "").lower(), "incomplete"),
                "current_period_end": _iso(data.get("current_period_end")),
                "cancel_at_period_end": bool(data.get("cancel_at_period_end") or False),
            },
        )
    elif event_type == "customer.subscription.deleted":
        _upsert_billing_account(client, msp_org_id, {"status": "canceled", "cancel_at_period_end": False})
    else:
        return msp_org_id
    propagate_to_clients(client, msp_org_id)
    # Quantities may have changed while checkout was open.
    if event_type.startswith("checkout.session."):
        sync_wholesale_quantities(client, settings, msp_org_id)
    return msp_org_id


def org_is_msp_billed(client: Any, org_id: str) -> bool:
    """True when a partner (MSP) pays for this workspace. Never raises."""
    try:
        rows = (
            client.table("org_billing")
            .select("billing_source")
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001 - column missing before migration: nothing is partner-billed
        return False
    return bool(rows and isinstance(rows[0], dict) and rows[0].get("billing_source") == "msp")


def assert_not_msp_billed(settings: Settings, org_id: str) -> None:
    """Block self-checkout for a workspace a partner already pays for."""
    from fastapi import HTTPException
    from supabase import create_client

    from app.core.db import shared_service_client

    try:
        client = shared_service_client(settings, create_client)
    except Exception:  # noqa: BLE001 - no client: same fail-open as before the migration
        return
    if org_is_msp_billed(client, org_id):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "BILLED_BY_PARTNER",
                "message": "This workspace is billed through your partner. Ask them to change your plan.",
            },
        )
