#!/usr/bin/env python3
"""Inspect org membership + platform admin for a user email."""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def load_env() -> dict[str, str]:
    repo = Path(__file__).resolve().parents[1]
    env: dict[str, str] = {}
    for path in (repo / "backend" / ".env", repo / "backend" / ".env.operator.local"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"')
    env.update({k: v for k, v in os.environ.items() if v})
    return env


def rest_get(base: str, service: str, path: str) -> list | dict:
    req = urllib.request.Request(
        f"{base}{path}",
        headers={"apikey": service, "Authorization": f"Bearer {service}"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def main() -> int:
    email = sys.argv[1] if len(sys.argv) > 1 else "cesar.bohorquez.jr@gmail.com"
    env = load_env()
    project = "smyeexlrqdpymwjmgzqu"
    base = f"https://{project}.supabase.co"
    service = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not service:
        print("Missing SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
        return 1

    q = urllib.parse.urlencode({"email": f"eq.{email}"})
    users = rest_get(base, service, f"/auth/v1/admin/users?{q}")
    rows = users.get("users") if isinstance(users, dict) else users
    if not rows:
        print("NO_AUTH_USER", email)
        return 0

    for user in rows:
        uid = user["id"]
        print("===", email, uid, "===")
        print("provider", (user.get("app_metadata") or {}).get("provider"))
        memberships = rest_get(
            base,
            service,
            f"/rest/v1/organization_members?user_id=eq.{uid}&select=org_id,role,created_at",
        )
        print("memberships", memberships)
        admins = rest_get(
            base,
            service,
            f"/rest/v1/platform_admins?user_id=eq.{uid}&select=user_id,email",
        )
        print("platform_admins", admins)
        app_users = rest_get(
            base,
            service,
            f"/rest/v1/users?auth_user_id=eq.{uid}&select=id,org_id,email,role,status",
        )
        print("public.users", app_users)
        if memberships:
            org_ids = ",".join(f'"{m["org_id"]}"' for m in memberships)
            orgs = rest_get(
                base,
                service,
                f"/rest/v1/organizations?id=in.({org_ids})&select=id,name,slug,status",
            )
            print("organizations", orgs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
