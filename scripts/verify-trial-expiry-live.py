"""Live production verification for trial-expiry P0 fix (Part A).

Creates a real org via Supabase auth signup (handle_new_user trigger), moves
trial_ends_at to the past in both storage locations, then verifies production API.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
ENV_BACKEND = REPO / "backend" / ".env"
ENV_OPERATOR = REPO / "backend" / ".env.operator.local"
API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (ENV_BACKEND, ENV_OPERATOR):
        if not path.is_file():
            continue
        merged.update({k: v for k, v in dotenv_values(path).items() if v})
    return merged


def _supabase_client(env: dict[str, str]):
    from supabase import create_client

    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET", "")
    supabase_url = (env.get("SUPABASE_URL") or "").rstrip("/")
    if not secret or not supabase_url:
        raise SystemExit("SUPABASE_JWT_SECRET required")
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


def _api_request(
    method: str,
    path: str,
    token: str,
    org_id: str,
    body: dict | None = None,
) -> tuple[int, dict | str]:
    url = f"{API_BASE}{path}"
    if "?" in path:
        url += "&environment=production" if "environment=" not in path else ""
    else:
        url += "?environment=production" if "environment=" not in path else ""

    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", "production")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def create_test_org(env: dict[str, str]) -> tuple[str, str, str, str]:
    """Create user via Supabase admin API (triggers handle_new_user)."""
    client = _supabase_client(env)
    ts = int(time.time())
    email = f"trial-expiry-test+{ts}@gravitre.app"
    password = f"TrialExpiry!{ts}X"

    created = client.auth.admin.create_user(
        {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": "Trial Expiry Live Test",
                "company_name": f"Trial Expiry Test {ts}",
            },
        }
    )
    user_id = str(created.user.id)

    # Wait for trigger to provision org
    for _ in range(10):
        members = (
            client.table("organization_members")
            .select("org_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if members.data:
            break
        time.sleep(0.5)
    else:
        raise SystemExit(f"handle_new_user did not provision org for user {user_id}")

    org_id = str(members.data[0]["org_id"])
    return org_id, user_id, email, password


def expire_trial(env: dict[str, str], org_id: str) -> dict:
    """Move trial end to the past in both organizations.settings and org_billing."""
    client = _supabase_client(env)
    expired_iso = (datetime.now(timezone.utc).replace(microsecond=0) - __import__("datetime").timedelta(days=1)).isoformat()

    org_row = (
        client.table("organizations")
        .select("settings")
        .eq("id", org_id)
        .limit(1)
        .execute()
    )
    settings = (org_row.data[0].get("settings") or {}) if org_row.data else {}
    billing_settings = dict(settings.get("billing") or {})
    billing_settings["trial_ends_at"] = expired_iso
    settings = dict(settings)
    settings["billing"] = billing_settings

    client.table("organizations").update({"settings": settings}).eq("id", org_id).execute()
    client.table("org_billing").update(
        {
            "billing_status": "trialing",
            "current_period_end": expired_iso,
        }
    ).eq("org_id", org_id).execute()

    billing = (
        client.table("org_billing")
        .select("billing_status, current_period_end")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    org_after = (
        client.table("organizations")
        .select("settings")
        .eq("id", org_id)
        .limit(1)
        .execute()
    )
    return {
        "expired_iso": expired_iso,
        "org_billing": billing.data[0] if billing.data else {},
        "settings_trial_ends_at": (
            (org_after.data[0].get("settings") or {}).get("billing", {}).get("trial_ends_at")
            if org_after.data
            else None
        ),
    }


def main() -> int:
    env = _load_env()
    print(f"Target API: {API_BASE}")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")

    org_id, user_id, email, _password = create_test_org(env)
    print(f"Created test org via signup trigger: org_id={org_id} user_id={user_id} email={email}")

    expiry = expire_trial(env, org_id)
    print(f"Expired trial: {json.dumps(expiry, indent=2)}")

    token = _mint_token(env, user_id, email)

    # A2 — gated endpoint
    status, body = _api_request(
        "POST",
        "/api/agent-jobs",
        token,
        org_id,
        {"task": "trial expiry live verification"},
    )
    print(f"\nA2 POST /api/agent-jobs -> HTTP {status}")
    print(json.dumps(body, indent=2) if isinstance(body, dict) else body)

    a2_pass = (
        status == 402
        and isinstance(body, dict)
        and body.get("error") == "plan_required"
        and body.get("subscription_status") == "trial_expired"
    )

    # A3 — allowlisted endpoints
    billing_status, billing_body = _api_request("GET", "/api/billing/status", token, org_id)
    print(f"\nA3 GET /api/billing/status -> HTTP {billing_status}")
    print(json.dumps(billing_body, indent=2) if isinstance(billing_body, dict) else billing_body)

    settings_status, settings_body = _api_request("GET", "/api/settings", token, org_id)
    print(f"\nA3 GET /api/settings -> HTTP {settings_status}")
    if isinstance(settings_body, dict):
        print(json.dumps({k: settings_body[k] for k in list(settings_body.keys())[:8]}, indent=2))
    else:
        print(settings_body)

    trial_expired_flag = False
    if isinstance(billing_body, dict):
        trial_expired_flag = bool(
            billing_body.get("trialExpired")
            or billing_body.get("trial_expired")
            or (billing_body.get("billingState") or {}).get("status") == "trial_expired"
        )

    a3_pass = billing_status == 200 and settings_status == 200 and trial_expired_flag

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test_org_id": org_id,
        "test_user_id": user_id,
        "test_email": email,
        "expiry": expiry,
        "a2_gated_endpoint": {"pass": a2_pass, "status": status, "body": body},
        "a3_allowlisted": {
            "pass": a3_pass,
            "billing_status": billing_status,
            "settings_status": settings_status,
            "trialExpired": trial_expired_flag,
        },
        "conclusion": "PASS" if a2_pass and a3_pass else "FAIL",
    }

    out_path = REPO / "docs" / "delivery" / "trial-expiry-live-verification.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")
    print(f"\nCONCLUSION: {result['conclusion']}")
    return 0 if a2_pass and a3_pass else 1


if __name__ == "__main__":
    sys.exit(main())
