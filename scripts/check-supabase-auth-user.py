#!/usr/bin/env python3
"""Check Supabase auth provider config and whether an email exists (no secrets printed)."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
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


def main() -> int:
    email = sys.argv[1] if len(sys.argv) > 1 else "cesar.bohorquez.jr@gmail.com"
    env = load_env()
    token = env.get("SUPABASE_ACCESS_TOKEN", "")
    project = env.get("SUPABASE_PROJECT_REF", "smyeexlrqdpymwjmgzqu")
    service = env.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if token:
        req = urllib.request.Request(
            f"https://api.supabase.com/v1/projects/{project}/config/auth",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                auth = json.load(resp)
        except urllib.error.HTTPError as exc:
            print("auth_config_error", exc.code, exc.read().decode()[:200])
        else:
            print("site_url", auth.get("site_url"))
            print("mailer_autoconfirm", auth.get("mailer_autoconfirm"))
            print("disable_signup", auth.get("disable_signup"))
            print("external_email_enabled", auth.get("external_email_enabled"))
            print("external_google_enabled", auth.get("external_google_enabled"))

    if service:
        query = urllib.parse.urlencode({"email": f"eq.{email}"})
        req = urllib.request.Request(
            f"https://{project}.supabase.co/auth/v1/admin/users?{query}",
            headers={
                "apikey": service,
                "Authorization": f"Bearer {service}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.load(resp)
        except urllib.error.HTTPError as exc:
            print("user_lookup_error", exc.code, exc.read().decode()[:200])
        else:
            users = payload.get("users") if isinstance(payload, dict) else payload
            if not users:
                print("user", email, "NOT_FOUND")
            else:
                user = users[0]
                print("user_found", email)
                print("email_confirmed_at", user.get("email_confirmed_at") or "NULL")
                print("last_sign_in_at", user.get("last_sign_in_at") or "NULL")
                print("providers", [i.get("provider") for i in (user.get("identities") or [])])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
