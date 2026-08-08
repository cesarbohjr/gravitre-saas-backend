"""Self-serve Voice Minutes top-up + bounded auto-top-up (Stripe payment mode)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.billing.stripe import init_stripe
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
        raise HTTPException(status_code=400, detail="Stripe customer required — complete plan checkout first")

    rate_cents = _rate_cents_per_minute(client, org_id)
    amount_cents = minutes * rate_cents
    amount_cents = min(amount_cents, HARD_MAX_CHARGE_CENTS)

    init_stripe(settings)
    import stripe

    pending = {
        "org_id": org_id,
        "metric_type": "voice_minutes",
        "minutes": minutes,
        "amount_cents": amount_cents,
        "currency": "usd",
        "source": "manual",
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
    client,
    *,
    session: dict[str, Any],
) -> dict[str, Any] | None:
    """Credit prepaid minutes after checkout.session.completed (payment mode)."""
    meta = session.get("metadata") if isinstance(session.get("metadata"), dict) else {}
    if str(meta.get("checkout_kind") or "") != "voice_minutes_topup":
        return None
    org_id = str(meta.get("org_id") or "").strip()
    minutes = int(meta.get("minutes") or 0)
    event_id = str(meta.get("topup_event_id") or "").strip()
    session_id = str(session.get("id") or "")
    payment_intent = session.get("payment_intent")
    if isinstance(payment_intent, dict):
        payment_intent = payment_intent.get("id")
    if not org_id or minutes <= 0:
        return None

    # Idempotent: already completed for this session?
    try:
        existing = (
            client.table("billing_topup_events")
            .select("id, status")
            .eq("stripe_checkout_session_id", session_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if existing and str(existing[0].get("status")) == "completed":
            return {"org_id": org_id, "minutes": minutes, "already_completed": True}
    except Exception:
        pass

    voice = load_voice_org_settings(client, org_id=org_id)
    new_prepaid = voice["voice_minutes_prepaid"] + minutes
    client.table("subscriptions").upsert(
        {"org_id": org_id, "voice_minutes_prepaid": new_prepaid},
        on_conflict="org_id",
    ).execute()

    now = datetime.now(timezone.utc).isoformat()
    update = {
        "status": "completed",
        "completed_at": now,
        "stripe_payment_intent_id": str(payment_intent or "") or None,
    }
    try:
        if event_id:
            client.table("billing_topup_events").update(update).eq("id", event_id).execute()
        elif session_id:
            client.table("billing_topup_events").update(update).eq(
                "stripe_checkout_session_id", session_id
            ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("topup_event_complete_failed error=%s", str(exc)[:160])

    return {"org_id": org_id, "minutes": minutes, "voice_minutes_prepaid": new_prepaid}


def maybe_auto_topup_voice_minutes(
    client,
    settings: Settings,
    *,
    org_id: str,
    remaining_minutes: int,
) -> dict[str, Any] | None:
    """Charge default payment method when remaining drops below threshold.

    Bounded by voice_auto_topup_max_charge_cents and HARD_MAX_CHARGE_CENTS.
    No-ops when voice is org-disabled or auto-top-up is off.
    """
    voice = load_voice_org_settings(client, org_id=org_id)
    if not voice["voice_enabled"] or not voice["voice_auto_topup_enabled"]:
        return None
    if remaining_minutes > voice["voice_auto_topup_threshold_minutes"]:
        return None

    minutes = int(voice["voice_auto_topup_minutes"])
    if minutes < 1:
        return None
    rate_cents = _rate_cents_per_minute(client, org_id)
    amount_cents = min(
        minutes * rate_cents,
        int(voice["voice_auto_topup_max_charge_cents"]),
        HARD_MAX_CHARGE_CENTS,
    )
    if amount_cents < 50:
        return None

    # Resolve Stripe customer
    try:
        rows = (
            client.table("org_billing")
            .select("stripe_customer_id")
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:
        rows = []
    customer_id = str((rows[0] or {}).get("stripe_customer_id") or "").strip()
    if not customer_id:
        logger.info("voice_auto_topup_skip_no_customer org_id=%s", org_id)
        return None

    init_stripe(settings)
    import stripe

    try:
        customer = stripe.Customer.retrieve(customer_id)
        pm = None
        invoice_settings = getattr(customer, "invoice_settings", None) or {}
        if isinstance(invoice_settings, dict):
            pm = invoice_settings.get("default_payment_method")
        if not pm:
            pms = stripe.PaymentMethod.list(customer=customer_id, type="card", limit=1)
            data = getattr(pms, "data", None) or []
            if data:
                pm = data[0].id
        if not pm:
            logger.info("voice_auto_topup_skip_no_pm org_id=%s", org_id)
            return None

        pending = {
            "org_id": org_id,
            "metric_type": "voice_minutes",
            "minutes": minutes,
            "amount_cents": amount_cents,
            "currency": "usd",
            "source": "auto",
            "status": "pending",
            "metadata": {"remaining_before": remaining_minutes},
        }
        inserted = client.table("billing_topup_events").insert(pending).execute()
        event_row = dict((inserted.data or [pending])[0])

        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            customer=customer_id,
            payment_method=pm if isinstance(pm, str) else getattr(pm, "id", pm),
            off_session=True,
            confirm=True,
            metadata={
                "org_id": org_id,
                "checkout_kind": "voice_minutes_topup",
                "topup_event_id": str(event_row.get("id") or ""),
                "minutes": str(minutes),
                "source": "auto",
            },
            description=f"Voice Minutes auto top-up ({minutes} min)",
        )
        if str(intent.status) != "succeeded":
            client.table("billing_topup_events").update({"status": "failed"}).eq(
                "id", event_row["id"]
            ).execute()
            return {"status": intent.status, "charged": False}

        new_prepaid = voice["voice_minutes_prepaid"] + minutes
        client.table("subscriptions").upsert(
            {"org_id": org_id, "voice_minutes_prepaid": new_prepaid},
            on_conflict="org_id",
        ).execute()
        now = datetime.now(timezone.utc).isoformat()
        client.table("billing_topup_events").update(
            {
                "status": "completed",
                "completed_at": now,
                "stripe_payment_intent_id": intent.id,
            }
        ).eq("id", event_row["id"]).execute()
        return {
            "charged": True,
            "minutes": minutes,
            "amount_cents": amount_cents,
            "voice_minutes_prepaid": new_prepaid,
            "payment_intent_id": intent.id,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("voice_auto_topup_failed org_id=%s error=%s", org_id, str(exc)[:200])
        return {"charged": False, "error": str(exc)[:200]}
