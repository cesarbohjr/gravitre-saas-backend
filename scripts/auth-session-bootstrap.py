#!/usr/bin/env python3
"""Mint a real Supabase session cookie for Playwright against gravitre.app.

Uses SUPABASE_SERVICE_ROLE_KEY + SUPABASE_JWT_SECRET to create (or update) a
password for the isolated conversation smoke user, then returns email/password
suitable for click-audit / chat-tti.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
    SA_EMAIL,
)


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (
        ROOT / "backend" / ".env.operator.local",
        ROOT / "backend" / ".env",
        ROOT / ".env",
    ):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def main() -> int:
    env = load_env()
    url = env["SUPABASE_URL"].rstrip("/")
    service = env["SUPABASE_SERVICE_ROLE_KEY"]
    user_id = env.get("ISOLATED_CONVERSATION_TEST_USER_ID") or DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID
    email = env.get("CLICK_AUDIT_EMAIL") or SA_EMAIL
    password = env.get("CLICK_AUDIT_PASSWORD") or secrets.token_urlsafe(24)

    headers = {
        "apikey": service,
        "Authorization": f"Bearer {service}",
        "Content-Type": "application/json",
    }
    # Update password for existing smoke user
    r = httpx.put(
        f"{url}/auth/v1/admin/users/{user_id}",
        headers=headers,
        json={"password": password, "email_confirm": True},
        timeout=60,
    )
    if r.status_code >= 400:
        # Try create
        r2 = httpx.post(
            f"{url}/auth/v1/admin/users",
            headers=headers,
            json={
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"full_name": "Gravitree Conversation Smoke SA"},
            },
            timeout=60,
        )
        if r2.status_code >= 400:
            print(json.dumps({"ok": False, "update": r.text[:500], "create": r2.text[:500]}))
            return 1
        data = r2.json()
        user_id = data.get("id") or user_id
        email = data.get("email") or email
    else:
        data = r.json()
        email = data.get("email") or email

    # Verify password grant works
    auth = httpx.post(
        f"{url}/auth/v1/token?grant_type=password",
        headers={"apikey": env["SUPABASE_ANON_KEY"], "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=60,
    )
    ok = auth.status_code < 400
    out = {
        "ok": ok,
        "email": email,
        "password": password,
        "user_id": user_id,
        "auth_status": auth.status_code,
    }
    path = ROOT / "docs" / "delivery" / "_phase4-auth-session.json"
    # Do not commit this file — local only
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "password"} | {"password_set": True}, indent=2))
    print(f"wrote {path} (gitignored locally; contains password)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
