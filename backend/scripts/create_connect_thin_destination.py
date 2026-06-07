"""Create Stripe Connect thin event destination for the v2 sample (one-time setup)."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

DESTINATION_URL = os.environ.get(
    "STRIPE_CONNECT_THIN_WEBHOOK_URL",
    "https://gravitre-saas-backend-production.up.railway.app/api/samples/stripe-connect/webhooks/thin",
)
API_VERSION = "2026-05-27.dahlia"


def main() -> int:
    api_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not api_key:
        print("ERROR: Set STRIPE_SECRET_KEY", file=sys.stderr)
        return 1

    payload = {
        "name": "Gravitre Connect v2 thin",
        "type": "webhook_endpoint",
        "event_payload": "thin",
        "events_from": ["@accounts"],
        "enabled_events": [
            "v2.core.account.updated",
            "v2.core.account.requirements.updated",
        ],
        "webhook_endpoint": {"url": DESTINATION_URL},
        "include": ["webhook_endpoint.url", "webhook_endpoint.signing_secret"],
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        "https://api.stripe.com/v2/core/event_destinations",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Stripe-Version": API_VERSION,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8"), file=sys.stderr)
        return 1

    secret = (
        (data.get("webhook_endpoint") or {}).get("signing_secret")
        if isinstance(data.get("webhook_endpoint"), dict)
        else None
    )
    print(json.dumps({"id": data.get("id"), "signing_secret": secret, "url": DESTINATION_URL}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
