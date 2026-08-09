"""Watch the open/fresh Voice Minutes Checkout until Stripe + DB show completed credit.

Usage (Railway prod env recommended):
  railway run python scripts/phase-c-close-watch-manual-topup.py
  railway run python scripts/phase-c-close-watch-manual-topup.py --session cs_live_...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
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
from app.config import get_settings  # noqa: E402

DEFAULT_SESSION = "cs_live_a1iVSZjrnmg8ImcSLPgBUENisOH0MtncgNxyYRJxfFHmXCeRihucp7Qu1o"
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", default=DEFAULT_SESSION)
    parser.add_argument("--timeout-sec", type=int, default=900)
    parser.add_argument("--poll-sec", type=int, default=8)
    args = parser.parse_args()

    settings = get_settings()
    init_stripe(settings)
    import stripe

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    deadline = time.time() + args.timeout_sec
    prepaid_before = 0
    try:
        row = (
            client.table("subscriptions")
            .select("voice_minutes_prepaid")
            .eq("org_id", ORG)
            .limit(1)
            .execute()
            .data
            or [{}]
        )[0]
        prepaid_before = int(row.get("voice_minutes_prepaid") or 0)
    except Exception:
        prepaid_before = 0

    print(
        json.dumps(
            {
                "watching_session": args.session,
                "org_id": ORG,
                "prepaid_before": prepaid_before,
                "checkout_hint": "Open the Stripe hosted URL and pay with a real card.",
            },
            indent=2,
        )
    )

    while time.time() < deadline:
        session = stripe.checkout.Session.retrieve(args.session)
        status = str(session.status)
        payment_status = str(session.payment_status)
        pi = session.payment_intent
        if isinstance(pi, dict):
            pi = pi.get("id")
        event_rows = (
            client.table("billing_topup_events")
            .select("id,status,minutes,amount_cents,stripe_payment_intent_id,completed_at")
            .eq("stripe_checkout_session_id", args.session)
            .limit(1)
            .execute()
            .data
            or []
        )
        event = event_rows[0] if event_rows else {}
        prepaid_now = prepaid_before
        try:
            prepaid_now = int(
                (
                    client.table("subscriptions")
                    .select("voice_minutes_prepaid")
                    .eq("org_id", ORG)
                    .limit(1)
                    .execute()
                    .data
                    or [{}]
                )[0].get("voice_minutes_prepaid")
                or 0
            )
        except Exception:
            pass

        snapshot = {
            "stripe_status": status,
            "payment_status": payment_status,
            "payment_intent": pi,
            "db_event_status": event.get("status"),
            "db_payment_intent": event.get("stripe_payment_intent_id"),
            "prepaid_before": prepaid_before,
            "prepaid_now": prepaid_now,
            "minutes_credited_delta": prepaid_now - prepaid_before,
        }
        ok = (
            status == "complete"
            and payment_status == "paid"
            and str(event.get("status") or "") == "completed"
            and prepaid_now >= prepaid_before + int(event.get("minutes") or 60)
        )
        if ok:
            print(json.dumps({"ok": True, **snapshot}, indent=2))
            return 0
        print(json.dumps({"ok": False, "waiting": True, **snapshot}, indent=2))
        if status in {"expired", "complete"} and payment_status != "paid":
            print(json.dumps({"ok": False, "terminal": True, **snapshot}, indent=2))
            return 1
        time.sleep(args.poll_sec)

    print(json.dumps({"ok": False, "timeout": True, "session": args.session}, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
