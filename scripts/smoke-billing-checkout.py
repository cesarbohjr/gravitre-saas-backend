"""Smoke test POST /api/billing/checkout against production."""
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
ENV_BACKEND = REPO / "backend" / ".env"
ENV_OPERATOR = REPO / "backend" / ".env.operator.local"
API_BASE = os.environ.get("BACKEND_URL", "https://gravitre.app").rstrip("/")


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (ENV_BACKEND, ENV_OPERATOR):
        if not path.is_file():
            continue
        merged.update({k: v for k, v in dotenv_values(path).items() if v})
    return merged


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET", "")
    supabase_url = (env.get("SUPABASE_URL") or "").rstrip("/")
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


def _checkout(url: str, token: str, org_id: str) -> tuple[int, str]:
    body = json.dumps({"plan_code": "node", "billing_interval": "monthly"}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def main() -> int:
    env = _load_env()
    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    ts = int(time.time())
    email = f"checkout-smoke+{ts}@gravitre.app"
    password = f"Checkout!{ts}X"
    created = client.auth.admin.create_user(
        {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": "Checkout Smoke",
                "company_name": f"Checkout Smoke {ts}",
            },
        }
    )
    user_id = str(created.user.id)
    org_id = None
    role = None
    for _ in range(10):
        members = (
            client.table("organization_members")
            .select("org_id, role")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if members.data:
            org_id = str(members.data[0]["org_id"])
            role = members.data[0].get("role")
            break
        time.sleep(0.5)

    if not org_id:
        print("FAIL: no org provisioned")
        return 1

    # Scenario: non-admin member cannot start checkout (require_admin).
    member_user = client.auth.admin.create_user(
        {
            "email": f"checkout-member+{ts}@gravitre.app",
            "password": password,
            "email_confirm": True,
        }
    )
    member_id = str(member_user.user.id)
    client.table("organization_members").insert(
        {"org_id": org_id, "user_id": member_id, "role": "member"}
    ).execute()

    token = _mint_token(env, user_id, email)
    member_token = _mint_token(env, member_id, f"checkout-member+{ts}@gravitre.app")
    print(f"user={email} org={org_id} role={role}")

    paths = [
        f"{API_BASE}/api/billing/checkout",
        "https://gravitre-saas-backend-production.up.railway.app/api/billing/checkout",
    ]
    ok = False
    for path in paths:
        status, body = _checkout(path, token, org_id)
        print(f"\nPOST {path} (admin)")
        print(f"HTTP {status}")
        print(body[:800])
        if status == 200 and "checkout_url" in body:
            ok = True

    member_status, member_body = _checkout(paths[0], member_token, org_id)
    print(f"\nPOST {paths[0]} (member)")
    print(f"HTTP {member_status}")
    print(member_body[:500])

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
