"""Disposable-org Phase C close: SetupIntent card attach → auto-top-up charge.

LIVE Stripe. Creates a throwaway org + customer, then pauses for YOU to attach
a real card on the Setup Checkout URL. After attach, burns remaining below
threshold and invokes maybe_auto_topup_voice_minutes.

Phases:
  railway run python scripts/phase-c-close-disposable-autotopup.py prepare
  # pay/attach card on printed URL
  railway run python scripts/phase-c-close-disposable-autotopup.py fire --org <org_id>
  railway run python scripts/phase-c-close-disposable-autotopup.py cleanup --org <org_id>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

for candidate in [ROOT / "backend" / ".env.operator.local", ROOT / "backend" / ".env"]:
    if not candidate.exists():
        continue
    for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value

from supabase import create_client  # noqa: E402

from app.billing.stripe import init_stripe  # noqa: E402
from app.billing.voice_topup import maybe_auto_topup_voice_minutes  # noqa: E402
from app.config import get_settings  # noqa: E402

STATE_PATH = ROOT / "docs" / "delivery" / "_phase_c_disposable_autotopup_state.json"


def _save_state(payload: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def prepare() -> int:
    settings = get_settings()
    init_stripe(settings)
    import stripe

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_id = str(uuid.uuid4())
    name = f"voice-autotopup-disposable-{org_id[:8]}"

    client.table("organizations").insert({"id": org_id, "name": name}).execute()
    # Minimal subscription row with tiny allotment + auto-top-up armed.
    client.table("subscriptions").upsert(
        {
            "org_id": org_id,
            "status": "active",
            "voice_enabled": True,
            "voice_minutes_prepaid": 0,
            "voice_auto_topup_enabled": True,
            "voice_auto_topup_minutes": 60,
            "voice_auto_topup_threshold_minutes": 15,
            "voice_auto_topup_max_charge_cents": 720,  # $7.20 = 60 min @ $0.12
            "meson_addons": [],
        },
        on_conflict="org_id",
    ).execute()

    customer = stripe.Customer.create(
        name=name,
        metadata={"org_id": org_id, "purpose": "phase_c_autotopup_disposable"},
    )
    client.table("org_billing").upsert(
        {
            "org_id": org_id,
            "stripe_customer_id": customer.id,
            "plan_code": "node",
            "billing_status": "active",
        },
        on_conflict="org_id",
    ).execute()

    app_url = (settings.public_app_url or "https://gravitre.app").rstrip("/")
    session = stripe.checkout.Session.create(
        mode="setup",
        customer=customer.id,
        currency="usd",
        success_url=f"{app_url}/settings/billing?autotopup_setup=success&org={org_id}",
        cancel_url=f"{app_url}/settings/billing?autotopup_setup=cancelled&org={org_id}",
        metadata={
            "org_id": org_id,
            "checkout_kind": "voice_autotopup_setup",
            "purpose": "phase_c_disposable",
        },
    )

    state = {
        "org_id": org_id,
        "org_name": name,
        "stripe_customer_id": customer.id,
        "setup_session_id": session.id,
        "setup_url": session.url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "auto_topup_minutes": 60,
        "auto_topup_threshold_minutes": 15,
        "max_charge_cents": 720,
        "expected_charge_usd": 7.20,
    }
    _save_state(state)
    print(
        json.dumps(
            {
                "ok": True,
                "phase": "prepare",
                "action_required": "Open setup_url and attach a REAL card (live mode). Then run fire.",
                **state,
                "next": f"railway run python scripts/phase-c-close-disposable-autotopup.py fire --org {org_id}",
            },
            indent=2,
        )
    )
    return 0


def fire(org_id: str) -> int:
    settings = get_settings()
    init_stripe(settings)
    import stripe

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    state = _load_state()
    if state.get("org_id") and state["org_id"] != org_id:
        print(json.dumps({"ok": False, "error": "org_id does not match saved state"}, indent=2))
        return 1

    billing = (
        client.table("org_billing")
        .select("stripe_customer_id")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or [{}]
    )[0]
    customer_id = str(billing.get("stripe_customer_id") or "")
    if not customer_id:
        print(json.dumps({"ok": False, "error": "missing stripe_customer_id"}, indent=2))
        return 1

    # Prefer default PM; else first card; else pull from completed setup session.
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
            stripe.Customer.modify(
                customer_id,
                invoice_settings={"default_payment_method": pm},
            )
    if not pm and state.get("setup_session_id"):
        setup_session = stripe.checkout.Session.retrieve(
            state["setup_session_id"], expand=["setup_intent"]
        )
        si = setup_session.setup_intent
        if isinstance(si, str):
            si = stripe.SetupIntent.retrieve(si)
        if si and getattr(si, "payment_method", None):
            pm = si.payment_method
            if isinstance(pm, dict):
                pm = pm.get("id")
            if pm:
                stripe.PaymentMethod.attach(pm, customer=customer_id)
                stripe.Customer.modify(
                    customer_id,
                    invoice_settings={"default_payment_method": pm},
                )

    if not pm:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "No payment method on disposable customer yet",
                    "setup_url": state.get("setup_url"),
                    "hint": "Complete the Setup Checkout with a real card, then re-run fire.",
                },
                indent=2,
            )
        )
        return 1

    # Burn: insert enough usage that remaining (included + prepaid - used) is below threshold.
    # Node included is typically 60; insert 50 used + prepaid 0 → remaining 10 <= threshold 15.
    period_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    client.table("usage_records").insert(
        {
            "org_id": org_id,
            "metric_type": "voice_minutes",
            "quantity": 50,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "source": "phase_c_autotopup_burn",
                "period_start": period_start.date().isoformat(),
            },
        }
    ).execute()

    # Ensure auto-top-up still armed and prepaid known.
    client.table("subscriptions").upsert(
        {
            "org_id": org_id,
            "voice_enabled": True,
            "voice_auto_topup_enabled": True,
            "voice_auto_topup_minutes": 60,
            "voice_auto_topup_threshold_minutes": 15,
            "voice_auto_topup_max_charge_cents": 720,
            "voice_minutes_prepaid": 0,
        },
        on_conflict="org_id",
    ).execute()

    remaining_before = 10  # 60 included - 50 used
    result = maybe_auto_topup_voice_minutes(
        client,
        settings,
        org_id=org_id,
        remaining_minutes=remaining_before,
    )

    events = (
        client.table("billing_topup_events")
        .select("*")
        .eq("org_id", org_id)
        .eq("source", "auto")
        .order("created_at", desc=True)
        .limit(3)
        .execute()
        .data
        or []
    )
    prepaid = (
        client.table("subscriptions")
        .select("voice_minutes_prepaid")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or [{}]
    )[0].get("voice_minutes_prepaid")

    ok = bool(result and result.get("charged")) and int(prepaid or 0) >= 60
    out = {
        "ok": ok,
        "phase": "fire",
        "org_id": org_id,
        "payment_method": pm if isinstance(pm, str) else getattr(pm, "id", pm),
        "remaining_before": remaining_before,
        "auto_topup_result": result,
        "latest_auto_events": [
            {
                "id": e.get("id"),
                "status": e.get("status"),
                "minutes": e.get("minutes"),
                "amount_cents": e.get("amount_cents"),
                "stripe_payment_intent_id": e.get("stripe_payment_intent_id"),
            }
            for e in events
        ],
        "voice_minutes_prepaid": prepaid,
        "cleanup": f"railway run python scripts/phase-c-close-disposable-autotopup.py cleanup --org {org_id}",
    }
    print(json.dumps(out, indent=2))
    state.update({"fire_result": out, "fired_at": datetime.now(timezone.utc).isoformat()})
    _save_state(state)
    return 0 if ok else 1


def cleanup(org_id: str) -> int:
    settings = get_settings()
    init_stripe(settings)
    import stripe

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    state = _load_state()
    customer_id = state.get("stripe_customer_id")
    billing = (
        client.table("org_billing")
        .select("stripe_customer_id")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or [{}]
    )[0]
    customer_id = customer_id or billing.get("stripe_customer_id")

    # Soft-delete app rows (keep Stripe PI history for audit).
    for table in ("billing_topup_events", "usage_records", "org_billing", "subscriptions"):
        try:
            client.table(table).delete().eq("org_id", org_id).execute()
        except Exception as exc:  # noqa: BLE001
            print(f"warn delete {table}: {exc}")
    try:
        client.table("organizations").delete().eq("id", org_id).execute()
    except Exception as exc:  # noqa: BLE001
        print(f"warn delete organizations: {exc}")

    if customer_id:
        try:
            stripe.Customer.delete(customer_id)
        except Exception as exc:  # noqa: BLE001
            print(f"warn stripe customer delete: {exc}")

    print(json.dumps({"ok": True, "phase": "cleanup", "org_id": org_id, "customer_id": customer_id}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "fire", "cleanup", "status"])
    parser.add_argument("--org", default="")
    args = parser.parse_args()
    if args.command == "prepare":
        return prepare()
    if args.command == "status":
        print(json.dumps(_load_state(), indent=2))
        return 0
    if not args.org:
        state = _load_state()
        args.org = str(state.get("org_id") or "")
    if not args.org:
        print(json.dumps({"ok": False, "error": "--org required"}, indent=2))
        return 1
    if args.command == "fire":
        return fire(args.org)
    return cleanup(args.org)


if __name__ == "__main__":
    raise SystemExit(main())
