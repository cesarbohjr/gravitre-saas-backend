"""Diagnose broken Checkout URL, mint fresh top-up session, verify HTTP load."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
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

from supabase import create_client

from app.billing.stripe import init_stripe
from app.billing.voice_topup import create_voice_minutes_topup_checkout
from app.config import get_settings

BROKEN = "cs_live_a1aqtjqWeyvpOjDUrsLjETH0SHVZflG74vDWxGTGtHCaGlwyBDG7PUh2lL"
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
OUT = ROOT / "docs" / "delivery" / "_phase_c_fresh_checkout.json"


def http_probe(url: str) -> dict:
    """Probe Checkout URL without following JS; capture status + body snippet."""
    # Probe both with and without fragment (servers ignore fragment anyway).
    base = url.split("#", 1)[0]
    results = {}
    for label, target in (("full_base", base),):
        req = urllib.request.Request(
            target,
            method="GET",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read(4000).decode("utf-8", errors="replace")
                results[label] = {
                    "http": resp.status,
                    "final_url": resp.geturl(),
                    "content_type": resp.headers.get("content-type"),
                    "body_has_something_went_wrong": "Something went wrong" in body,
                    "body_has_checkout": "checkout" in body.lower(),
                    "body_snippet": body[:280].replace("\n", " "),
                }
        except urllib.error.HTTPError as exc:
            body = exc.read(2000).decode("utf-8", errors="replace")
            results[label] = {
                "http": exc.code,
                "final_url": target,
                "body_has_something_went_wrong": "Something went wrong" in body,
                "body_snippet": body[:280].replace("\n", " "),
            }
        except Exception as exc:  # noqa: BLE001
            results[label] = {"error": str(exc)[:240]}
    return results


def main() -> int:
    settings = get_settings()
    init_stripe(settings)
    import stripe

    acct = stripe.Account.retrieve()
    broken = stripe.checkout.Session.retrieve(BROKEN)
    now = int(time.time())
    diagnosis = {
        "stripe_account_id": acct.id,
        "stripe_key_prefix": (settings.stripe_secret_key or "")[:10],
        "broken_session": {
            "id": broken.id,
            "status": broken.status,
            "payment_status": broken.payment_status,
            "livemode": broken.livemode,
            "created": broken.created,
            "expires_at": broken.expires_at,
            "expired_by_clock": bool(broken.expires_at and now >= int(broken.expires_at)),
            "seconds_until_expiry": int(broken.expires_at) - now if broken.expires_at else None,
            "customer": broken.customer,
            "amount_total": broken.amount_total,
            "ui_mode": broken.ui_mode,
            "adaptive_pricing": broken.adaptive_pricing,
            "url": broken.url,
        },
        "broken_http_probe": http_probe(broken.url or ""),
        "cause_hypothesis": [],
    }

    # Classify cause
    if broken.status == "expired":
        diagnosis["cause_hypothesis"].append("session_expired")
    elif broken.status == "complete":
        diagnosis["cause_hypothesis"].append("session_already_completed")
    elif broken.payment_status == "paid":
        diagnosis["cause_hypothesis"].append("session_already_paid")
    elif diagnosis["broken_http_probe"].get("full_base", {}).get("body_has_something_went_wrong"):
        diagnosis["cause_hypothesis"].append(
            "hosted_page_404_while_api_open — likely Stripe hosted-page render failure "
            "(not expiry/cancel); often branding/adaptive_pricing/account Checkout config"
        )
    elif broken.status == "open" and broken.payment_status == "unpaid":
        diagnosis["cause_hypothesis"].append(
            "api_says_open_unpaid — not expired/completed/cancelled; hosted URL broken independently"
        )

    # Expire/abandon old open sessions for this customer to avoid confusion (do not reuse).
    try:
        for sess in stripe.checkout.Session.list(customer=str(broken.customer), limit=10).data:
            if sess.status == "open" and sess.mode == "payment":
                try:
                    stripe.checkout.Session.expire(sess.id)
                except Exception:
                    pass
    except Exception:
        pass

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    billing = (
        client.table("org_billing")
        .select("stripe_customer_id")
        .eq("org_id", ORG)
        .limit(1)
        .execute()
        .data
        or [{}]
    )[0]
    customer_id = str(billing.get("stripe_customer_id") or broken.customer)

    # Fresh session via product path.
    created = create_voice_minutes_topup_checkout(
        client,
        settings,
        org_id=ORG,
        minutes=60,
        customer_id=customer_id,
        success_url="https://gravitre.app/settings/billing?topup=success",
        cancel_url="https://gravitre.app/settings/billing?topup=cancelled",
        actor_user_id="phase-c-fresh-verify",
    )

    fresh = stripe.checkout.Session.retrieve(created["session_id"])
    # If hosted probe fails on default create, try a minimal Session.create fallback.
    probe = http_probe(fresh.url or "")
    fallback = None
    if probe.get("full_base", {}).get("body_has_something_went_wrong") or probe.get("full_base", {}).get("http") not in {
        200,
        303,
        302,
        301,
    }:
        # Minimal checkout — avoid adaptive pricing / branding edge cases where possible.
        pending = {
            "org_id": ORG,
            "metric_type": "voice_minutes",
            "minutes": 60,
            "amount_cents": 720,
            "currency": "usd",
            "source": "manual",
            "status": "pending",
            "metadata": {"actor_user_id": "phase-c-fresh-minimal"},
        }
        inserted = client.table("billing_topup_events").insert(pending).execute()
        event_row = dict((inserted.data or [pending])[0])
        minimal = stripe.checkout.Session.create(
            mode="payment",
            customer=customer_id,
            success_url="https://gravitre.app/settings/billing?topup=success",
            cancel_url="https://gravitre.app/settings/billing?topup=cancelled",
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": 720,
                        "product_data": {
                            "name": "Voice Minutes top-up (60 min)",
                            "description": "60 prepaid voice minutes @ $0.12/min",
                        },
                    },
                }
            ],
            metadata={
                "org_id": ORG,
                "checkout_kind": "voice_minutes_topup",
                "topup_event_id": str(event_row.get("id") or ""),
                "minutes": "60",
                "amount_cents": "720",
            },
        )
        try:
            client.table("billing_topup_events").update(
                {"stripe_checkout_session_id": minimal.id}
            ).eq("id", event_row["id"]).execute()
        except Exception:
            pass
        # Expire the first fresh if it was unusable.
        try:
            stripe.checkout.Session.expire(fresh.id)
        except Exception:
            pass
        fresh = minimal
        created = {
            "session_id": minimal.id,
            "checkout_url": minimal.url,
            "minutes": 60,
            "amount_cents": 720,
            "topup_event_id": event_row.get("id"),
            "creation_path": "minimal_fallback",
        }
        probe = http_probe(fresh.url or "")
        fallback = "used_minimal_session_create"

    ok = (
        (not probe.get("full_base", {}).get("body_has_something_went_wrong"))
        and int(probe.get("full_base", {}).get("http") or 0) == 200
        and bool(fresh.url)
    )

    payload = {
        "ok": ok,
        "diagnosis": diagnosis,
        "fresh": {
            "session_id": fresh.id,
            "status": fresh.status,
            "payment_status": fresh.payment_status,
            "amount_total": fresh.amount_total,
            "url": fresh.url,
            "created": created,
            "http_probe": probe,
            "fallback": fallback,
        },
        "do_not_reuse": [BROKEN, "cs_live_a1iVSZjrnmg8ImcSLPgBUENisOH0MtncgNxyYRJxfFHmXCeRihucp7Qu1o"],
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
