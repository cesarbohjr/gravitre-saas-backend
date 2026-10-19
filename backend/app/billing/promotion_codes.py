"""Public promotion codes (e.g. LAUNCH30) backed by Stripe Coupons + PromotionCodes.

Separation from founder offers (``commercial_offers.py``):

* A founder offer is issued to one reviewed external org and applied
  automatically. A public code is created once and usable by anyone.
* They never stack. When an org holds an available founder offer, the founder
  coupon is applied and any promo code is ignored (the API says so).
* Stripe is authoritative for validity, redemption limits, expiry, first-time
  restrictions and the discounted amount. Local rows are the admin catalog and
  redemption evidence; a local "valid" never overrides a Stripe rejection.

Discount selection at checkout (``checkout_discount``):

1. founder offer available            -> founder coupon / trial, code ignored
2. promo code supplied and valid      -> ``discounts=[{promotion_code: id}]``
3. promo code supplied but invalid    -> 422 with a customer-safe reason
4. nothing supplied, codes enabled    -> ``allow_promotion_codes=True`` (Stripe field)
5. codes disabled                     -> neither
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

import stripe
from fastapi import HTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)

PLAN_CODES: tuple[str, ...] = ("node", "control", "command")
PLAN_LABELS = {"node": "Node", "control": "Control", "command": "Command"}
CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,39}$")

# One message for every "no" so validation cannot be used to learn which codes
# exist, have expired or are exhausted.
INVALID_CODE_MESSAGE = "This promo code isn't valid or has expired."
CODES_DISABLED_MESSAGE = "Promo codes aren't available right now."
FOUNDER_OFFER_WINS_MESSAGE = (
    "Your founder offer is applied instead. Promo codes can't be combined with it."
)


def promotion_codes_enabled(settings: Any) -> bool:
    return getattr(settings, "promotion_codes_enabled", True) is True


def normalize_code(code: str | None) -> str | None:
    value = (code or "").strip().upper()
    if not value or not CODE_PATTERN.match(value):
        return None
    return value


def normalize_plan(plan_code: str | None) -> str | None:
    from app.billing.stripe import _normalize_plan_code

    plan = _normalize_plan_code(plan_code)
    return plan if plan in PLAN_CODES else None


def _utc(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _money(cents: int, currency: str | None) -> str:
    cur = (currency or "usd").lower()
    amount = cents / 100
    text = f"{amount:,.0f}" if cents % 100 == 0 else f"{amount:,.2f}"
    return f"${text}" if cur == "usd" else f"{text} {cur.upper()}"


def describe_discount(
    *,
    percent_off: Any = None,
    amount_off_cents: Any = None,
    currency: str | None = None,
    duration: str | None = None,
    duration_in_months: Any = None,
) -> str:
    """Human summary, e.g. '30% off for 3 months' or '$20 off your first payment'."""
    if percent_off not in (None, ""):
        pct = float(percent_off)
        value = f"{pct:g}% off"
    elif amount_off_cents not in (None, ""):
        value = f"{_money(int(amount_off_cents), currency)} off"
    else:
        return "Discount"
    if duration == "once":
        return f"{value} your first payment"
    if duration == "forever":
        return f"{value} every billing period"
    months = int(duration_in_months or 0)
    if months:
        return f"{value} for {months} month{'s' if months != 1 else ''}"
    return value


def describe_row(row: dict[str, Any]) -> str:
    summary = describe_discount(
        percent_off=row.get("percent_off"),
        amount_off_cents=row.get("amount_off_cents"),
        currency=row.get("currency"),
        duration=row.get("duration"),
        duration_in_months=row.get("duration_in_months"),
    )
    plans = [p for p in (row.get("restricted_plan_codes") or []) if p in PLAN_LABELS]
    if plans and len(plans) < len(PLAN_CODES):
        summary += " on " + " or ".join(PLAN_LABELS[p] for p in plans)
    if row.get("first_time_only"):
        summary += " (new customers only)"
    return summary


def _attr(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    try:
        return obj.get(key)  # StripeObject
    except Exception:  # noqa: BLE001
        return getattr(obj, key, None)


def promotion_code_coupon(promo: Any) -> Any:
    """Coupon of a PromotionCode across Stripe API versions.

    Clover (2025-09-30+) nests it under ``promotion.coupon``; earlier versions
    expose ``coupon`` directly. Either may be an id or an expanded object.
    """
    promotion = _attr(promo, "promotion")
    if promotion:
        coupon = _attr(promotion, "coupon")
        if coupon:
            return coupon
    return _attr(promo, "coupon")


def stripe_create_promotion_code(coupon_id: str, **kwargs: Any) -> Any:
    """Create a PromotionCode on any API version (Clover shape first)."""
    try:
        return stripe.PromotionCode.create(
            promotion={"type": "coupon", "coupon": coupon_id}, **kwargs
        )
    except stripe.error.InvalidRequestError as exc:
        if "promotion" not in str(exc).lower():
            raise
        return stripe.PromotionCode.create(coupon=coupon_id, **kwargs)


def base_plan_products(settings: Any, plans: Iterable[str] | None = None) -> list[str]:
    """Stripe base-plan products for ``plans`` (default: all), excluding metered add-ons.

    Mirrors the founder-offer restriction so a public 30%-off code can never
    discount AI-credit, voice or research overage prices.
    """
    from app.billing.stripe import init_stripe, price_id_for_plan

    init_stripe(settings)
    wanted = [p for p in (plans or PLAN_CODES) if p in PLAN_CODES] or list(PLAN_CODES)
    products: set[str] = set()
    for plan in wanted:
        if not price_id_for_plan(settings, plan, billing_interval="monthly"):
            raise HTTPException(status_code=503, detail=f"Missing Stripe base price for {plan}")
        for interval in ("monthly", "annual"):
            price_id = price_id_for_plan(settings, plan, billing_interval=interval)
            if not price_id:
                continue
            product = stripe.Price.retrieve(price_id).get("product")
            product_id = product.get("id") if isinstance(product, dict) else product
            if not isinstance(product_id, str) or not product_id.startswith("prod_"):
                raise HTTPException(status_code=503, detail="Unable to verify Stripe base plan product")
            products.add(product_id)
    if not products:
        raise HTTPException(status_code=503, detail="No Stripe base plan products available")
    return sorted(products)


# ---------------------------------------------------------------------------
# Admin lifecycle
# ---------------------------------------------------------------------------


def record_event(
    client: Any,
    *,
    dedupe_key: str,
    event_type: str,
    promotion_code_id: str | None,
    stripe_promotion_code_id: str | None,
    actor_id: str | None = None,
    org_id: str | None = None,
    details: dict | None = None,
) -> None:
    try:
        client.table("promotion_code_events").insert(
            {
                "dedupe_key": dedupe_key,
                "event_type": event_type,
                "promotion_code_id": promotion_code_id,
                "stripe_promotion_code_id": stripe_promotion_code_id,
                "actor_id": actor_id,
                "org_id": org_id,
                "details": details or {},
            }
        ).execute()
    except Exception:  # noqa: BLE001 — evidence must not undo a Stripe change
        logger.exception("promotion_code_event_persist_failed type=%s key=%s", event_type, dedupe_key)


def validate_create_request(body: Any) -> dict[str, Any]:
    """Normalize and check an admin create request. Raises 422 with a reason."""
    code = normalize_code(body.code)
    if not code:
        raise HTTPException(
            status_code=422,
            detail="Codes are 3-40 characters: letters, numbers, dashes or underscores",
        )
    if (body.percent_off is None) == (body.amount_off_cents is None):
        raise HTTPException(status_code=422, detail="Set either percent_off or amount_off_cents")
    if body.amount_off_cents is not None and (body.currency or "usd").lower() != "usd":
        raise HTTPException(status_code=422, detail="Fixed-amount codes must be in USD")
    if body.duration == "repeating":
        if not body.duration_in_months:
            raise HTTPException(status_code=422, detail="Repeating codes need duration_in_months")
    elif body.duration_in_months is not None:
        raise HTTPException(status_code=422, detail="duration_in_months only applies to repeating codes")
    if body.expires_at is not None:
        if body.expires_at.tzinfo is None:
            raise HTTPException(status_code=422, detail="Expiry requires a timezone")
        if body.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=422, detail="Expiry must be in the future")
    plans = sorted({p for p in (body.plan_codes or [])})
    if any(p not in PLAN_CODES for p in plans):
        raise HTTPException(status_code=422, detail="Unknown plan restriction")
    if set(plans) == set(PLAN_CODES):
        plans = []
    return {
        "code": code,
        "percent_off": body.percent_off,
        "amount_off_cents": body.amount_off_cents,
        "currency": "usd" if body.amount_off_cents is not None else None,
        "duration": body.duration,
        "duration_in_months": body.duration_in_months,
        "max_redemptions": body.max_redemptions,
        "expires_at": body.expires_at,
        "first_time_only": bool(body.first_time_only),
        "restricted_plan_codes": plans,
    }


def create_promotion_code(client: Any, settings: Any, spec: dict[str, Any], actor_id: str) -> dict:
    """Create Coupon + PromotionCode in Stripe, then persist the catalog row.

    The Coupon is restricted to base-plan products (all plans or the chosen
    subset). If PromotionCode creation fails the Coupon is deleted so no
    orphan discount is left behind.
    """
    if not promotion_codes_enabled(settings):
        raise HTTPException(status_code=503, detail="Promo codes are disabled (PROMOTION_CODES_ENABLED=false)")
    if not getattr(settings, "stripe_secret_key", ""):
        raise HTTPException(
            status_code=503,
            detail="Stripe is not configured (STRIPE_SECRET_KEY); promo codes cannot be created",
        )
    existing = (
        client.table("promotion_codes").select("id").eq("code", spec["code"]).eq("active", True).limit(1).execute().data
        or []
    )
    if existing:
        raise HTTPException(status_code=409, detail="An active code with that name already exists")
    from app.billing.stripe import init_stripe

    init_stripe(settings)
    summary = describe_row(spec)
    coupon_args: dict[str, Any] = {
        "applies_to": {"products": base_plan_products(settings, spec["restricted_plan_codes"] or None)},
        "duration": spec["duration"],
        "name": f"{spec['code']}: {summary}"[:40],
        "metadata": {"kind": "public_promotion_code", "code": spec["code"], "created_by": str(actor_id)},
    }
    if spec["percent_off"] is not None:
        coupon_args["percent_off"] = spec["percent_off"]
    else:
        coupon_args["amount_off"] = spec["amount_off_cents"]
        coupon_args["currency"] = spec["currency"]
    if spec["duration"] == "repeating":
        coupon_args["duration_in_months"] = spec["duration_in_months"]
    coupon = stripe.Coupon.create(**coupon_args)
    promo_args: dict[str, Any] = {
        "code": spec["code"],
        "metadata": {"kind": "public_promotion_code", "created_by": str(actor_id)},
    }
    if spec["max_redemptions"]:
        promo_args["max_redemptions"] = spec["max_redemptions"]
    if spec["expires_at"]:
        promo_args["expires_at"] = int(spec["expires_at"].timestamp())
    if spec["first_time_only"]:
        promo_args["restrictions"] = {"first_time_transaction": True}
    try:
        promo = stripe_create_promotion_code(coupon["id"], **promo_args)
    except stripe.error.StripeError:
        try:
            stripe.Coupon.delete(coupon["id"])
        except stripe.error.StripeError:
            logger.exception("promotion_code_orphan_coupon coupon=%s", coupon["id"])
        raise
    row = {
        "stripe_promotion_code_id": promo["id"],
        "stripe_coupon_id": coupon["id"],
        "code": spec["code"],
        "percent_off": spec["percent_off"],
        "amount_off_cents": spec["amount_off_cents"],
        "currency": spec["currency"],
        "duration": spec["duration"],
        "duration_in_months": spec["duration_in_months"],
        "max_redemptions": spec["max_redemptions"],
        "expires_at": spec["expires_at"].isoformat() if spec["expires_at"] else None,
        "first_time_only": spec["first_time_only"],
        "restricted_plan_codes": spec["restricted_plan_codes"],
        "active": True,
        "created_by": actor_id,
    }
    inserted = client.table("promotion_codes").insert(row).execute().data or []
    if not inserted:
        # Stripe has a live code we could not record: deactivate it rather
        # than leave an uncatalogued public discount.
        try:
            stripe.PromotionCode.modify(promo["id"], active=False)
        except stripe.error.StripeError:
            logger.exception("promotion_code_uncatalogued promo=%s", promo["id"])
        raise HTTPException(status_code=502, detail="Could not persist promo code; it was deactivated in Stripe")
    saved = inserted[0]
    record_event(
        client,
        dedupe_key=f"created:{promo['id']}",
        event_type="created",
        promotion_code_id=str(saved["id"]),
        stripe_promotion_code_id=promo["id"],
        actor_id=actor_id,
        details={"code": spec["code"], "summary": summary},
    )
    return {**saved, "summary": summary, "status": "active"}


def code_status(row: dict[str, Any], *, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if not row.get("active"):
        return "inactive"
    expires = _utc(row.get("expires_at"))
    if expires and expires <= now:
        return "expired"
    max_r = row.get("max_redemptions")
    if max_r and int(row.get("times_redeemed") or 0) >= int(max_r):
        return "exhausted"
    return "active"


def list_promotion_codes(client: Any, settings: Any, *, refresh: bool = True) -> dict[str, Any]:
    """Catalog rows, refreshing redemption counts / active flags from Stripe."""
    rows = (
        client.table("promotion_codes").select("*").order("created_at", desc=True).limit(200).execute().data or []
    )
    synced = False
    sync_error = None
    if refresh and rows and getattr(settings, "stripe_secret_key", ""):
        from app.billing.stripe import init_stripe

        init_stripe(settings)
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            for row in rows:
                promo = stripe.PromotionCode.retrieve(row["stripe_promotion_code_id"])
                remote_count = int(promo.get("times_redeemed") or 0)
                remote_active = bool(promo.get("active"))
                patch: dict[str, Any] = {"redemption_count_synced_at": now_iso}
                if remote_count != int(row.get("times_redeemed") or 0):
                    patch["times_redeemed"] = remote_count
                if not remote_active and row.get("active"):
                    patch["active"] = False
                    patch["deactivated_at"] = row.get("deactivated_at") or now_iso
                client.table("promotion_codes").update({**patch, "updated_at": now_iso}).eq("id", row["id"]).execute()
                row.update(patch)
            synced = True
        except stripe.error.StripeError as exc:
            sync_error = getattr(exc, "user_message", None) or "Stripe refresh failed"
            logger.warning("promotion_code_refresh_failed err=%s", type(exc).__name__)
    return {
        "enabled": promotion_codes_enabled(settings),
        "stripe_configured": bool(getattr(settings, "stripe_secret_key", "")),
        "synced_with_stripe": synced,
        "sync_error": sync_error,
        "codes": [{**row, "summary": describe_row(row), "status": code_status(row)} for row in rows],
    }


def deactivate_promotion_code(client: Any, settings: Any, code_id: str, actor_id: str) -> dict:
    rows = client.table("promotion_codes").select("*").eq("id", code_id).limit(1).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Promo code not found")
    row = rows[0]
    if getattr(settings, "stripe_secret_key", ""):
        from app.billing.stripe import init_stripe

        init_stripe(settings)
        # Stripe first: a local-only deactivation would leave the code redeemable.
        stripe.PromotionCode.modify(row["stripe_promotion_code_id"], active=False)
    elif row.get("active"):
        raise HTTPException(status_code=503, detail="Stripe is not configured; cannot deactivate the Stripe code")
    now_iso = datetime.now(timezone.utc).isoformat()
    client.table("promotion_codes").update(
        {"active": False, "deactivated_by": actor_id, "deactivated_at": now_iso, "updated_at": now_iso}
    ).eq("id", code_id).execute()
    record_event(
        client,
        dedupe_key=f"deactivated:{row['stripe_promotion_code_id']}",
        event_type="deactivated",
        promotion_code_id=code_id,
        stripe_promotion_code_id=row["stripe_promotion_code_id"],
        actor_id=actor_id,
        details={"code": row.get("code")},
    )
    return {"id": code_id, "code": row.get("code"), "active": False, "status": "inactive"}


# ---------------------------------------------------------------------------
# Customer validation and checkout selection
# ---------------------------------------------------------------------------


def _invalid(reason: str = INVALID_CODE_MESSAGE) -> dict[str, Any]:
    return {"valid": False, "summary": None, "reason": reason}


def validate_promotion_code(
    client: Any,
    settings: Any,
    code: str | None,
    plan_code: str | None = None,
    *,
    verify_with_stripe: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Customer-safe validation. Invalid results never reveal why, except a
    plan mismatch on an otherwise valid code (so the customer can switch plan)."""
    if not promotion_codes_enabled(settings):
        return _invalid(CODES_DISABLED_MESSAGE)
    normalized = normalize_code(code)
    if not normalized:
        return _invalid()
    rows = (
        client.table("promotion_codes")
        .select("*")
        .eq("code", normalized)
        .eq("active", True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows or code_status(rows[0], now=now) != "active":
        return _invalid()
    row = rows[0]
    if verify_with_stripe and getattr(settings, "stripe_secret_key", ""):
        from app.billing.stripe import init_stripe

        init_stripe(settings)
        try:
            promo = stripe.PromotionCode.retrieve(row["stripe_promotion_code_id"], expand=["promotion.coupon"])
        except stripe.error.InvalidRequestError:
            try:
                promo = stripe.PromotionCode.retrieve(row["stripe_promotion_code_id"])
            except stripe.error.StripeError:
                return _invalid()
        except stripe.error.StripeError:
            return _invalid("We couldn't check this code right now. Try again in a moment.")
        coupon = promotion_code_coupon(promo)
        if not promo.get("active") or (isinstance(coupon, dict) and coupon.get("valid") is False):
            return _invalid()
    plan = normalize_plan(plan_code)
    restricted = [p for p in (row.get("restricted_plan_codes") or []) if p in PLAN_CODES]
    summary = describe_row(row)
    if plan and restricted and plan not in restricted:
        names = " or ".join(PLAN_LABELS[p] for p in restricted)
        return {"valid": False, "summary": summary, "reason": f"This code only applies to {names}."}
    return {
        "valid": True,
        "code": row["code"],
        "summary": summary,
        "reason": None,
        "percent_off": float(row["percent_off"]) if row.get("percent_off") is not None else None,
        "amount_off_cents": row.get("amount_off_cents"),
        "currency": row.get("currency"),
        "duration": row.get("duration"),
        "duration_in_months": row.get("duration_in_months"),
        "plan_codes": restricted or list(PLAN_CODES),
        "first_time_only": bool(row.get("first_time_only")),
        "expires_at": row.get("expires_at"),
        "_stripe_promotion_code_id": row["stripe_promotion_code_id"],
    }


def public_validation(result: dict[str, Any]) -> dict[str, Any]:
    """Strip internal identifiers before returning validation to a browser."""
    return {k: v for k, v in result.items() if not k.startswith("_")}


def checkout_discount(
    client: Any,
    settings: Any,
    *,
    promotion_code: str | None,
    plan_code: str | None,
    founder_offer: dict[str, Any] | None,
) -> dict[str, Any]:
    """Pick exactly one discount mechanism for a checkout (see module docstring)."""
    supplied = (promotion_code or "").strip()
    if founder_offer:
        return {
            "mode": "founder_offer",
            "promotion_code_ignored": bool(supplied),
            "notice": FOUNDER_OFFER_WINS_MESSAGE if supplied else None,
        }
    if supplied:
        if not promotion_codes_enabled(settings):
            raise HTTPException(status_code=422, detail=CODES_DISABLED_MESSAGE)
        result = validate_promotion_code(client, settings, supplied, plan_code)
        if not result.get("valid"):
            raise HTTPException(status_code=422, detail=result.get("reason") or INVALID_CODE_MESSAGE)
        return {
            "mode": "promotion_code",
            "stripe_promotion_code_id": result["_stripe_promotion_code_id"],
            "code": result["code"],
            "summary": result["summary"],
        }
    if promotion_codes_enabled(settings):
        return {"mode": "stripe_field"}
    return {"mode": "none"}


def checkout_session_kwargs(discount: dict[str, Any] | None) -> dict[str, Any]:
    """Arguments for ``create_checkout_session`` from a ``checkout_discount`` result."""
    discount = discount or {}
    if discount.get("mode") == "promotion_code":
        return {
            "promotion_code_id": discount["stripe_promotion_code_id"],
            "promotion_code": discount.get("code"),
        }
    if discount.get("mode") == "stripe_field":
        return {"allow_promotion_codes": True}
    return {}


def checkout_response_fields(discount: dict[str, Any] | None) -> dict[str, Any]:
    discount = discount or {}
    fields: dict[str, Any] = {"discount_source": discount.get("mode") or "none"}
    if discount.get("mode") == "promotion_code":
        fields["promotion_code"] = discount.get("code")
        fields["discount_summary"] = discount.get("summary")
    if discount.get("promotion_code_ignored"):
        fields["promotion_code_ignored"] = True
        fields["notice"] = discount.get("notice")
    return fields


# ---------------------------------------------------------------------------
# Webhook redemption evidence
# ---------------------------------------------------------------------------


def _id_of(value: Any) -> str | None:
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        found = value.get("id")
        return str(found) if found else None
    return None


def _promotion_ids_from_discounts(discounts: Any) -> list[str]:
    ids: list[str] = []
    for entry in discounts or []:
        if isinstance(entry, dict):
            promo = _id_of(entry.get("promotion_code"))
            if promo and promo.startswith("promo_"):
                ids.append(promo)
    return ids


def redemption_signals(event_type: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract (promotion code, subscription) pairs from a signed Stripe event.

    * ``checkout.session.completed``: hosted checkout, whether we applied the
      code or the customer typed it into Stripe's own field.
    * ``invoice.paid`` / ``invoice.payment_succeeded`` with billing_reason
      ``subscription_create``: the in-app Payment Element flow.
    """
    if not isinstance(data, dict):
        return []
    promo_ids: list[str] = []
    subscription_id: str | None = None
    session_id = invoice_id = None
    if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        if data.get("mode") not in (None, "subscription"):
            return []
        subscription_id = _id_of(data.get("subscription"))
        session_id = data.get("id")
        promo_ids = _promotion_ids_from_discounts(data.get("discounts"))
        meta_id = str((data.get("metadata") or {}).get("promotion_code_id") or "")
        if meta_id.startswith("promo_"):
            promo_ids.append(meta_id)
    elif event_type in {"invoice.paid", "invoice.payment_succeeded"}:
        if data.get("billing_reason") != "subscription_create":
            return []
        invoice_id = data.get("id")
        parent = data.get("parent") or {}
        details = (parent.get("subscription_details") if isinstance(parent, dict) else None) or data.get(
            "subscription_details"
        ) or {}
        subscription_id = _id_of(data.get("subscription")) or _id_of(details.get("subscription"))
        promo_ids = _promotion_ids_from_discounts(data.get("discounts"))
        legacy = data.get("discount")
        if isinstance(legacy, dict):
            promo_ids += _promotion_ids_from_discounts([legacy])
        meta_id = str((details.get("metadata") or {}).get("promotion_code_id") or "")
        if meta_id.startswith("promo_"):
            promo_ids.append(meta_id)
    else:
        return []
    if not subscription_id:
        return []
    seen: list[str] = []
    for promo in promo_ids:
        if promo not in seen:
            seen.append(promo)
    return [
        {
            "stripe_promotion_code_id": promo,
            "stripe_subscription_id": subscription_id,
            "checkout_session_id": session_id,
            "invoice_id": invoice_id,
        }
        for promo in seen
    ]


def record_redemptions_from_event(
    client: Any, settings: Any, event_type: str, data: dict[str, Any], org_id: str | None
) -> list[str]:
    """Persist exactly-once redemption evidence. Never raises into the webhook."""
    recorded: list[str] = []
    try:
        signals = redemption_signals(event_type, data)
    except Exception:  # noqa: BLE001
        logger.exception("promotion_code_redemption_parse_failed type=%s", event_type)
        return recorded
    for signal in signals:
        try:
            created = client.rpc(
                "record_promotion_code_redemption",
                {
                    "p_dedupe_key": f"redeemed:{signal['stripe_promotion_code_id']}:{signal['stripe_subscription_id']}",
                    "p_stripe_promotion_code_id": signal["stripe_promotion_code_id"],
                    "p_org_id": org_id,
                    "p_source_event": event_type,
                    "p_details": {
                        "subscription_id": signal["stripe_subscription_id"],
                        "checkout_session_id": signal.get("checkout_session_id"),
                        "invoice_id": signal.get("invoice_id"),
                    },
                },
            ).execute().data
            if created is True or created == [True]:
                recorded.append(signal["stripe_promotion_code_id"])
        except Exception:  # noqa: BLE001 — list refresh re-syncs counts from Stripe
            logger.exception(
                "promotion_code_redemption_persist_failed promo=%s", signal["stripe_promotion_code_id"]
            )
    return recorded


# ---------------------------------------------------------------------------
# Customer-facing discount on the current subscription
# ---------------------------------------------------------------------------


def active_subscription_discount(settings: Any, subscription_id: str | None) -> dict[str, Any] | None:
    """Current Stripe discount on a subscription, e.g. 30% off until a date."""
    if not subscription_id or not getattr(settings, "stripe_secret_key", ""):
        return None
    from app.billing.stripe import init_stripe

    init_stripe(settings)
    try:
        subscription = stripe.Subscription.retrieve(subscription_id, expand=["discounts"])
    except stripe.error.InvalidRequestError:
        subscription = stripe.Subscription.retrieve(subscription_id)
    candidates: list[Any] = [d for d in (subscription.get("discounts") or []) if d and not isinstance(d, str)]
    legacy = subscription.get("discount")
    if legacy and not isinstance(legacy, str):
        candidates.append(legacy)
    for discount in candidates:
        # Clover nests the coupon under ``source``; older versions expose it directly.
        coupon = _attr(discount, "coupon") or _attr(_attr(discount, "source") or {}, "coupon")
        if isinstance(coupon, str):
            try:
                coupon = stripe.Coupon.retrieve(coupon)
            except stripe.error.StripeError:
                continue
        if not coupon:
            continue
        end = _attr(discount, "end")
        percent = _attr(coupon, "percent_off")
        amount = _attr(coupon, "amount_off")
        label = describe_discount(percent_off=percent, amount_off_cents=amount, currency=_attr(coupon, "currency"))
        return {
            "label": label,
            "summary": describe_discount(
                percent_off=percent,
                amount_off_cents=amount,
                currency=_attr(coupon, "currency"),
                duration=_attr(coupon, "duration"),
                duration_in_months=_attr(coupon, "duration_in_months"),
            ),
            "percent_off": percent,
            "amount_off_cents": amount,
            "currency": _attr(coupon, "currency"),
            "duration": _attr(coupon, "duration"),
            "ends_at": _utc(end).isoformat() if end else None,
            "source": (
                "promotion_code"
                if _attr(discount, "promotion_code")
                else "founder_offer"
                if (_attr(coupon, "metadata") or {}).get("issued_by")
                else "coupon"
            ),
        }
    return None
