#!/usr/bin/env python3
"""Mint a smoke-user magic link that can establish a real browser session.

Root cause (2026-09-21): generate_link with redirect_to=/ai lands hash tokens on
a protected route. proxy.ts redirects to /login and drops the hash, so
hasSession stays false.

Correct redirect_to is the public auth callback (hash handoff or token_hash).
Writes e2e/.fixtures/magic-link.txt for consume-link.mjs (gitignored).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlencode

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "e2e" / ".fixtures"
EMAIL_DEFAULT = "conversation-smoke-sa@gravitre.app"
CALLBACK_DEFAULT = "https://gravitre.app/auth/callback?next=/ai"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (
        REPO / "backend" / ".env",
        REPO / "backend" / ".env.operator.local",
        REPO / "apps" / "web" / ".env.local",
        REPO / ".env",
    ):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            pass
    return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=EMAIL_DEFAULT)
    parser.add_argument("--redirect-to", default=CALLBACK_DEFAULT)
    parser.add_argument(
        "--prefer",
        choices=("callback_url", "action_link"),
        default="callback_url",
        help="callback_url uses hashed_token on /auth/callback (server verifyOtp).",
    )
    args = parser.parse_args()

    env = _load_env()
    url = env.get("SUPABASE_URL") or env.get("NEXT_PUBLIC_SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
        return 2

    from supabase import create_client

    sb = create_client(url, key)
    res = sb.auth.admin.generate_link(
        {
            "type": "magiclink",
            "email": args.email,
            "options": {"redirect_to": args.redirect_to},
        }
    )
    props = getattr(res, "properties", None) or {}
    action_link = getattr(props, "action_link", None) or (
        props.get("action_link") if isinstance(props, dict) else None
    )
    hashed = getattr(props, "hashed_token", None) or (
        props.get("hashed_token") if isinstance(props, dict) else None
    )
    vtype = (
        getattr(props, "verification_type", None)
        or (props.get("verification_type") if isinstance(props, dict) else None)
        or "magiclink"
    )

    OUT.mkdir(parents=True, exist_ok=True)
    if args.prefer == "callback_url" and hashed:
        qs = urlencode({"token_hash": hashed, "type": vtype, "next": "/ai"})
        link = f"https://gravitre.app/auth/callback?{qs}"
        mode = "token_hash_callback"
    else:
        link = str(action_link or "")
        mode = "action_link"
        if not link:
            print("generate_link returned no action_link / hashed_token", file=sys.stderr)
            return 1

    (OUT / "magic-link.txt").write_text(link + "\n", encoding="utf-8")
    summary = {
        "mode": mode,
        "email": args.email,
        "redirect_to": args.redirect_to,
        "has_hashed_token": bool(hashed),
        "link_host_path": link.split("?")[0],
        "res_type": type(res).__name__,
    }
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
