"""Self-serve Voice Minutes top-up + bounded auto-top-up (Stripe payment mode)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.billing.stripe import init_stripe
from app.billing.safety import record_billing_alert
from app.billing.voice_access import load_voice_org_settings
from app.billing.voice_minutes_plan_rates import overage_usd_per_voice_minute
from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Packs offered in the UI (minutes → charged at live overage rate).
VOICE_TOPUP_PACKS = (60, 300, 1200)
# Absolute ceiling even if admin misconfigures max_charge_cents.
HARD_MAX_CHARGE_CENTS = 12000  # $120


def _rate_cents_per_minute(client, org_id: str) -> int:
    from app.billing.service import get_plan_for_org

    plan = get_plan_for_org(client, org_id)
    rate = overage_usd_per_voice_minute(plan)
    return max(int(round(float(rate) * 100)), 1)


def create_voice_minutes_topup_checkout(
    client,
    settings: Settings,
    *,
    org_id: str,
    minutes: int,
    customer_id: str,
    success_url: str,
    cancel_url: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    voice = load_voice_org_settings(client, org_id=org_id)
    if not voice["voice_enabled"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voice is disabled for this organization — enable it before topping up",
        )
    minutes = int(minutes)
    if minutes not in VOICE_TOPUP_PACKS:
        raise HTTPException(
            status_code=400,
            detail=f"minutes must be one of {list(VOICE_TOPUP_PACKS)}",
        )
    if not customer_id:
        raise HTTPException(
            status_code=400,
            detail="Stripe customer required — complete plan checkout first",
        )

    rate_cents = _rate_cents_per_minute(client, org_id)
    amount_cents = minutes * rate_cents
    if amount_cents > HARD_MAX_CHARGE_CENTS:
        raise HTTPException(
            status_code=422,
            detail="Selected pack exceeds the maximum charge; choose a smaller pack",
        )

    init_stripe(settings)
    import stripe

    pending = {
        "org_id": org_id,
        "metric_type": "voice_minutes",
        "minutes": minutes,
        "amount_cents": amount_cents,
        "currency": "usd",
        "source": "manual",
        "stripe_customer_id": customer_id,
        "status": "pending",
        "metadata": {"actor_user_id": actor_user_id or "", "rate_cents": rate_cents},
    }
    inserted = client.table("billing_topup_events").insert(pending).execute()
    event_row = dict((inserted.data or [pending])[0])

    session = stripe.checkout.Session.create(
        mode="payment",
        customer=customer_id,
        success_url=success_url,
        cancel_url=cancel_url,
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": "usd",
                    "unit_amount": amount_cents,
                    "product_data": {
                        "name": f"Voice Minutes top-up ({minutes} min)",
                        "description": f"{minutes} prepaid voice minutes @ ${rate_cents / 100:.2f}/min",
                    },
                },
            }
        ],
        metadata={
            "org_id": org_id,
            "checkout_kind": "voice_minutes_topup",
            "topup_event_id": str(event_row.get("id") or ""),
            "minutes": str(minutes),
            "amount_cents": str(amount_cents),
        },
    )
    try:
        client.table("billing_topup_events").update(
            {"stripe_checkout_session_id": session.id}
        ).eq("id", event_row["id"]).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("topup_event_session_link_failed error=%s", str(exc)[:160])

    return {
        "checkout_url": session.url,
        "session_id": session.id,
        "minutes": minutes,
        "amount_cents": amount_cents,
        "rate_cents_per_minute": rate_cents,
        "topup_event_id": event_row.get("id"),
    }


def fulfill_voice_minutes_topup(
    client, *, session: dict[str, Any]
) -> dict[str, Any] | None:
    """Paid, identity-checked, atomic and exactly-once prepaid credit."""
    meta = session.get("metadata") if isinstance(session.get("metadata"), dict) else {}
    if meta.get("checkout_kind") != "voice_minutes_topup":
        return None
    if session.get("payment_status") != "paid" or session.get("mode") != "payment":
        return None
    intent = session.get("payment_intent")
    if isinstance(intent, dict):
        intent = intent.get("id")
    if not meta.get("topup_event_id") or not meta.get("org_id") or not intent:
        raise ValueError("Topup payment identity missing")
    result = (
        client.rpc(
            "complete_voice_topup",
            {
                "p_event_id": meta["topup_event_id"],
                "p_org_id": meta["org_id"],
                "p_customer": session.get("customer"),
                "p_amount": int(session.get("amount_total") or 0),
                "p_currency": session.get("currency"),
                "p_payment_intent": str(intent),
                "p_session": str(session.get("id") or ""),
            },
        )
        .execute()
        .data
    )
    if not isinstance(result, dict):
        raise ValueError("Topup completion not verified")
    return result


def maybe_auto_topup_voice_minutes(
    client, settings: Settings, *, org_id: str, remaining_minutes: int
) -> dict[str, Any] | None:
    """Only explicitly enabled, active paid accounts; claim before any charge.

    A pending attempt remains fenced on every ambiguous outcome. Trials cannot
    be auto-charged. Per-charge and monthly limits bound the complete pack price.
    """
    voice = load_voice_org_settings(client, org_id=org_id)
    if (
        not voice["voice_enabled"]
        or not voice["voice_auto_topup_enabled"]
        or voice["subscription_status"] != "active"
    ):
        return None
    if remaining_minutes > voice["voice_auto_topup_threshold_minutes"]:
        return None
    minutes = int(voice["voice_auto_topup_minutes"])
    amount = minutes * _rate_cents_per_minute(client, org_id)
    if amount < 50 or amount > min(
        int(voice["voice_auto_topup_max_charge_cents"]), HARD_MAX_CHARGE_CENTS
    ):
        return {"charged": False, "error": "topup_pack_exceeds_charge_cap"}
    from app.billing.service import get_plan_for_org
    from app.billing.voice_minutes_plan_rates import included_voice_minutes_for_plan
    import stripe

    event = None
    try:
        included = included_voice_minutes_for_plan(get_plan_for_org(client, org_id))
        event = (
            client.rpc(
                "claim_voice_auto_topup",
                {
                    "p_org_id": org_id,
                    "p_minutes": minutes,
                    "p_amount": amount,
                    "p_included": included,
                },
            )
            .execute()
            .data
        )
        if not isinstance(event, dict) or not event.get("id"):
            return {"charged": False, "reason": "quota_cap_or_pending_attempt"}
        remote = stripe.StripeClient(settings.stripe_secret_key)
        customer_id = event["stripe_customer_id"]
        subscription = remote.v1.subscriptions.retrieve(event["stripe_subscription_id"])
        if (
            subscription.get("status") != "active"
            or subscription.get("customer") != customer_id
        ):
            raise ValueError("active_stripe_subscription_required")
        customer = remote.v1.customers.retrieve(customer_id)
        if (customer.get("metadata") or {}).get("org_id") != org_id:
            raise ValueError("stripe_customer_org_mismatch")
        pm = (customer.get("invoice_settings") or {}).get(
            "default_payment_method"
        ) or subscription.get("default_payment_method")
        if isinstance(pm, dict):
            pm = pm.get("id")
        if not pm:
            raise ValueError("explicit_default_payment_method_required")
        intent = remote.v1.payment_intents.create(
            {
                "amount": amount,
                "currency": "usd",
                "customer": customer_id,
                "payment_method": pm,
                "off_session": True,
                "confirm": True,
                "metadata": {
                    "org_id": org_id,
                    "checkout_kind": "voice_minutes_topup",
                    "topup_event_id": str(event["id"]),
                },
            },
            options={"idempotency_key": f"voice-auto-topup:{event['id']}"},
        )
        client.table("billing_topup_events").update(
            {"stripe_payment_intent_id": intent["id"]}
        ).eq("id", event["id"]).eq("status", "pending").execute()
        if intent.get("status") != "succeeded":
            raise ValueError("payment_requires_reconciliation")
        credited = (
            client.rpc(
                "complete_voice_topup",
                {
                    "p_event_id": str(event["id"]),
                    "p_org_id": org_id,
                    "p_customer": customer_id,
                    "p_amount": int(intent.get("amount_received") or 0),
                    "p_currency": intent.get("currency"),
                    "p_payment_intent": intent["id"],
                    "p_session": "",
                },
            )
            .execute()
            .data
        )
        if not isinstance(credited, dict):
            raise ValueError("Topup credit not verified")
        return {
            "charged": True,
            "minutes": minutes,
            "amount_cents": amount,
            "payment_intent_id": intent["id"],
            **credited,
        }
    except Exception as exc:
        record_billing_alert(
            client,
            kind="voice_auto_topup_requires_review",
            key=f"topup:{event['id'] if isinstance(event,dict) and event.get('id') else org_id}",
            org_id=org_id,
            details={"error_class": type(exc).__name__},
        )
        logger.warning(
            "voice_auto_topup_requires_review org_id=%s error_class=%s",
            org_id,
            type(exc).__name__,
        )
        return {"charged": False, "requires_reconciliation": True}
