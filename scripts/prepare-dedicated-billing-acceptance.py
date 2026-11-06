"""Validate existing sandbox pricing and forward signed test webhooks to CI only.

Does not provision Stripe products/prices, register a webhook endpoint, or change
Supabase schema. The listener dies with the disposable hosted runner.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import time

from billing_acceptance_safety import require_isolated_target, verify_test_price


def prepare(*, client_factory=None, popen=subprocess.Popen, sleep=time.sleep) -> None:
    require_isolated_target(os.environ.get("SUPABASE_URL", ""))
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    public_key = os.environ.get("NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY", "")
    if not key.startswith("sk_test_") or not public_key.startswith("pk_test_"):
        raise ValueError("Dedicated acceptance requires sk_test_ and matching pk_test_ credentials")
    price_id = os.environ.get("STRIPE_PRICE_ID_NODE_MONTHLY", "")
    if not price_id:
        raise ValueError("Missing acceptance Node monthly price")
    if client_factory is None:
        import stripe
        client_factory = stripe.StripeClient
    client = client_factory(key)
    try:
        price = client.v1.prices.retrieve(price_id)
    except Exception:
        # Stripe errors may contain configuration values. Retain only the check.
        raise ValueError("Acceptance price lookup failed with the test key; verify test-mode account and price") from None
    verify_test_price(price)
    print("Verified existing sandbox price: active, livemode=false, USD 59/month, licensed (ID redacted)")

    root = Path(os.environ["RUNNER_TEMP"])
    log = root / "dedicated-billing-stripe-listener.log"
    command = ["npx", "--yes", "@stripe/cli@1.54.0", "--config", str(root / "dedicated-billing-stripe.toml"),
               "listen", "--events", "checkout.session.completed,checkout.session.async_payment_succeeded,"
               "customer.subscription.created,customer.subscription.updated,customer.subscription.deleted,"
               "invoice.paid,invoice.payment_failed",
               "--forward-to", "http://127.0.0.1:8000/api/webhooks/stripe"]
    with log.open("w") as output:
        listener = popen(command, stdout=output, stderr=subprocess.STDOUT,
                         start_new_session=True, env={**os.environ, "STRIPE_API_KEY": key})
    (root / "dedicated-billing-stripe-listener.pid").write_text(str(listener.pid))
    for _ in range(90):
        found = re.search(r"whsec_[A-Za-z0-9]+", log.read_text(errors="replace"))
        if found:
            secret = found.group()
            print("::add-mask::" + secret)
            with Path(os.environ["GITHUB_ENV"]).open("a") as output:
                output.write("STRIPE_WEBHOOK_SECRET=" + secret + "\n")
            print("Signed Stripe test-event forwarding ready for runner-local backend")
            return
        if listener.poll() is not None:
            raise RuntimeError("Stripe test listener exited before readiness (raw log withheld)")
        sleep(1)
    raise RuntimeError("Stripe test listener did not become ready")


if __name__ == "__main__":
    try:
        prepare()
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from None
