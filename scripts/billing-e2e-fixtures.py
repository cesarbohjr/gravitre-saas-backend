"""Repeatable billing E2E user/org fixtures (Supabase admin API).

Writes credentials to e2e/.fixtures/billing-users.json for Playwright globalSetup.
Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (backend/.env.operator.local).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
ENV_BACKEND = REPO / "backend" / ".env"
ENV_OPERATOR = REPO / "backend" / ".env.operator.local"
FIXTURES_PATH = REPO / "e2e" / ".fixtures" / "billing-users.json"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (ENV_BACKEND, ENV_OPERATOR):
        if not path.is_file():
            continue
        merged.update({k: v for k, v in dotenv_values(path).items() if v})
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if os.environ.get(key):
            merged[key] = os.environ[key]
    return merged


def _supabase_client(env: dict[str, str]):
    from supabase import create_client

    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required for billing E2E fixtures")
    return create_client(url, key)


def _create_user(client, label: str) -> tuple[str, str, str, str]:
    ts = int(time.time())
    email = f"billing-e2e+{label}+{ts}@gravitre.app"
    password = f"BillingE2e!{label}{ts}X"
    created = client.auth.admin.create_user(
        {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": f"Billing E2E {label}",
                "company_name": f"Billing E2E {label} {ts}",
            },
        }
    )
    user_id = str(created.user.id)
    for _ in range(15):
        members = (
            client.table("organization_members")
            .select("org_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if members.data:
            org_id = str(members.data[0]["org_id"])
            return org_id, user_id, email, password
        time.sleep(0.4)
    raise RuntimeError(f"handle_new_user did not provision org for {email}")


def _set_trial_window(
    client,
    org_id: str,
    *,
    ends_at: datetime,
    billing_status: str = "trialing",
) -> None:
    iso = ends_at.replace(microsecond=0).isoformat()
    org_row = (
        client.table("organizations")
        .select("settings")
        .eq("id", org_id)
        .limit(1)
        .execute()
    )
    settings = dict((org_row.data[0].get("settings") or {}) if org_row.data else {})
    billing_settings = dict(settings.get("billing") or {})
    billing_settings["trial_ends_at"] = iso
    settings["billing"] = billing_settings
    client.table("organizations").update({"settings": settings}).eq("id", org_id).execute()
    client.table("org_billing").update(
        {
            "billing_status": billing_status,
            "current_period_end": iso,
        }
    ).eq("org_id", org_id).execute()


def build_fixtures() -> dict:
    env = _load_env()
    client = _supabase_client(env)
    now = datetime.now(timezone.utc)

    expired_org, expired_user, expired_email, expired_password = _create_user(client, "expired")
    _set_trial_window(client, expired_org, ends_at=now - timedelta(days=1))

    active_org, active_user, active_email, active_password = _create_user(client, "active")
    _set_trial_window(client, active_org, ends_at=now + timedelta(days=5))

    canceled_org, canceled_user, canceled_email, canceled_password = _create_user(client, "canceled")
    _set_trial_window(
        client,
        canceled_org,
        ends_at=now - timedelta(days=1),
        billing_status="cancelled",
    )

    return {
        "generatedAt": now.isoformat(),
        "expiredTrial": {
            "orgId": expired_org,
            "userId": expired_user,
            "email": expired_email,
            "password": expired_password,
        },
        "activeTrial": {
            "orgId": active_org,
            "userId": active_user,
            "email": active_email,
            "password": active_password,
        },
        "canceledWithExpiredTrial": {
            "orgId": canceled_org,
            "userId": canceled_user,
            "email": canceled_email,
            "password": canceled_password,
        },
    }


def main() -> int:
    fixtures = build_fixtures()
    FIXTURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURES_PATH.write_text(json.dumps(fixtures, indent=2), encoding="utf-8")
    print(f"Wrote billing E2E fixtures to {FIXTURES_PATH}")
    for key in ("expiredTrial", "activeTrial", "canceledWithExpiredTrial"):
        row = fixtures[key]
        print(f"  {key}: {row['email']} org={row['orgId']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
