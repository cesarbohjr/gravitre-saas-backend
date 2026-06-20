"""Production smoke: M4 marketplace routes + Stripe checkout session creation."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
API_BASE = os.environ.get(
    "BACKEND_URL",
    "https://api.gravitre.app",
).rstrip("/")
SMOKE_PAID_SLUG = "smoke-paid-operator-pack"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (REPO / "backend" / ".env", REPO / "backend" / ".env.operator.local"):
        if path.is_file():
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
    return merged


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET") or os.environ.get("SUPABASE_JWT_SECRET", "")
    supabase_url = (env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")).rstrip("/")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{supabase_url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _request(
    path: str,
    token: str,
    org_id: str,
    *,
    method: str = "GET",
    body: dict | None = None,
) -> tuple[int, dict]:
    url = f"{API_BASE}{path}"
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
            return resp.status, payload
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read().decode("utf-8", errors="replace") or "{}")
        return exc.code, payload if isinstance(payload, dict) else {"raw": payload}


def main() -> int:
    env = _load_env()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if env.get(key) and not os.environ.get(key):
            os.environ[key] = env[key]

    simulate = "--simulate-fulfillment" in sys.argv
    skip_stripe = "--skip-stripe" in sys.argv

    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    members = (
        client.table("organization_members")
        .select("org_id,user_id,role")
        .eq("role", "admin")
        .limit(1)
        .execute()
    )
    row = (members.data or [{}])[0]
    org_id = str(row["org_id"])
    user_id = str(row["user_id"])
    users = client.auth.admin.get_user_by_id(user_id)
    email = (users.user.email if users and users.user else None) or f"{user_id}@gravitre.local"
    token = _mint_token(env, user_id, email)
    print(f"using org_id={org_id} api={API_BASE}")

    paid = (
        client.table("marketplace_assets")
        .select("id, slug, pricing_type, price_cents")
        .eq("slug", SMOKE_PAID_SLUG)
        .limit(1)
        .execute()
    )
    if not paid.data:
        print(f"paid smoke asset missing: run scripts/ensure_marketplace_smoke_paid_asset.py", file=sys.stderr)
        return 1
    paid_asset = paid.data[0]
    slug = str(paid_asset["slug"])
    print(f"paid asset: {slug} ({paid_asset.get('pricing_type')} {paid_asset.get('price_cents')} cents)")

    status, entitlement = _request(
        f"/api/marketplace/assets/{slug}/entitlement",
        token,
        org_id,
    )
    if status != 200:
        print(f"entitlement failed: HTTP {status} {entitlement}", file=sys.stderr)
        return 1
    print(
        f"entitlement: requiresPayment={entitlement.get('requiresPayment')} "
        f"hasEntitlement={entitlement.get('hasEntitlement')}"
    )

    if skip_stripe:
        print("skip-stripe: checkout probe skipped")
        return 0

    # Clear prior active entitlement so checkout can be recreated.
    client.table("marketplace_asset_entitlements").update({"status": "cancelled"}).eq(
        "org_id", org_id
    ).eq("asset_id", paid_asset["id"]).eq("status", "active").execute()
    client.table("marketplace_asset_entitlements").update({"status": "cancelled"}).eq(
        "org_id", org_id
    ).eq("asset_id", paid_asset["id"]).eq("status", "pending").execute()

    app_url = (
        env.get("NEXT_PUBLIC_APP_URL")
        or os.environ.get("NEXT_PUBLIC_APP_URL")
        or "https://gravitre.app"
    ).rstrip("/")
    status, checkout = _request(
        f"/api/marketplace/assets/{slug}/checkout",
        token,
        org_id,
        method="POST",
        body={
            "successUrl": f"{app_url}/marketplace/assets/{slug}?purchase=success",
            "cancelUrl": f"{app_url}/marketplace/assets/{slug}?purchase=cancelled",
        },
    )
    if status not in {200, 201}:
        print(f"checkout failed: HTTP {status} {checkout}", file=sys.stderr)
        return 1

    checkout_url = checkout.get("checkoutUrl") or checkout.get("checkout_url")
    session_id = checkout.get("sessionId") or checkout.get("session_id")
    entitlement_id = checkout.get("entitlementId") or checkout.get("entitlement_id")
    if not checkout_url or not session_id:
        print(f"checkout response missing url/session: {checkout}", file=sys.stderr)
        return 1
    print(f"checkout session: {session_id}")
    print(f"checkout url: {checkout_url}")

    stripe_key = env.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_SECRET_KEY", "")
    if not stripe_key.strip():
        print("STRIPE_SECRET_KEY not set locally — checkout created on API; open URL to complete payment")
        return 0

    sys.path.insert(0, str(REPO / "backend"))
    os.environ.setdefault("STRIPE_SECRET_KEY", stripe_key)
    from app.config import get_settings
    from app.billing.stripe import init_stripe

    init_stripe(get_settings())
    import stripe

    session = stripe.checkout.Session.retrieve(session_id)
    print(f"stripe session status={session.status} mode={session.mode} amount={session.amount_total}")

    if simulate and entitlement_id:
        from app.marketplace.entitlements import fulfill_entitlement_from_checkout

        fulfilled = fulfill_entitlement_from_checkout(
            client,
            get_settings(),
            session={
                "id": session_id,
                "payment_intent": session.payment_intent,
                "subscription": session.subscription,
                "metadata": dict(session.metadata or {}),
                "client_reference_id": entitlement_id,
            },
        )
        if not fulfilled:
            print("simulate-fulfillment failed", file=sys.stderr)
            return 1
        print(f"simulated fulfillment: entitlement={fulfilled.get('id')} status={fulfilled.get('status')}")

        status, check = _request(
            f"/api/marketplace/assets/{slug}/install-check",
            token,
            org_id,
        )
        if status != 200 or not check.get("hasEntitlement"):
            print(f"post-fulfillment install-check failed: {check}", file=sys.stderr)
            return 1
        print("install-check confirms hasEntitlement after simulated fulfillment")

    print("OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        raise SystemExit(1) from exc
