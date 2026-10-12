#!/usr/bin/env python3
"""Mint a short-lived session for the isolated smoke-org service account.

Uses the same mechanism as the AI hardening smoke and the Voice SLO probe: the
smoke org and service-account actor come from the conversation write guard
(``resolve_isolated_conversation_actor``) and the token is an HS256 Supabase
access token signed with SUPABASE_JWT_SECRET. Nothing is provisioned here: the
org, the service account and its membership must already exist, or the script
fails closed. The operator org is refused by the guard.

With ``--github-env`` the token is masked in the job log and exported for later
steps as PLATFORM_LIVE_BEARER_TOKEN / PLATFORM_LIVE_ORG_ID, with
PLATFORM_LIVE_AUTH_MODE=smoke_org_short_lived. The token is never printed.

Required: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

import jwt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import resolve_isolated_conversation_actor

TOKEN_TTL_SECONDS = 600
AUTH_MODE = "smoke_org_short_lived"


class SmokeSessionError(RuntimeError):
    """The smoke org or its service account is not in the expected state."""


def _required(env: dict[str, str], name: str) -> str:
    value = str(env.get(name) or "").strip()
    if not value:
        raise SmokeSessionError(f"missing required environment variable: {name}")
    return value


def verify_smoke_actor(client: Any, org_id: str, user_id: str) -> None:
    """Read-only check that the org is the flagged smoke org and the SA is a member."""
    org = (
        client.table("organizations")
        .select("id,settings")
        .eq("id", org_id)
        .limit(1)
        .execute()
    )
    rows = getattr(org, "data", None) or []
    settings = (rows[0] or {}).get("settings") if rows else None
    if (
        not isinstance(settings, dict)
        or settings.get("isolated_conversation_test_org") is not True
    ):
        raise SmokeSessionError(
            "smoke org is missing or not flagged isolated_conversation_test_org"
        )
    member = (
        client.table("organization_members")
        .select("id")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not (getattr(member, "data", None) or []):
        raise SmokeSessionError(
            "smoke service account is not a member of the smoke org"
        )


def mint_token(
    *,
    supabase_url: str,
    secret: str,
    user_id: str,
    email: str,
    now: float | None = None,
) -> str:
    iat = int(time.time() if now is None else now)
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{supabase_url.rstrip('/')}/auth/v1",
            "iat": iat,
            "exp": iat + TOKEN_TTL_SECONDS,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def mint_session(env: dict[str, str], client: Any) -> tuple[str, str]:
    """Return (token, org_id) for the smoke-org service account."""
    url = _required(env, "SUPABASE_URL")
    secret = _required(env, "SUPABASE_JWT_SECRET")
    org_id, user_id, email = resolve_isolated_conversation_actor(
        dict(env), client, provision=False
    )
    verify_smoke_actor(client, org_id, user_id)
    return mint_token(
        supabase_url=url, secret=secret, user_id=user_id, email=email
    ), org_id


def export_to_github(token: str, org_id: str, github_env: Path) -> None:
    # Mask before the value can reach any log line.
    print(f"::add-mask::{token}", flush=True)
    with github_env.open("a", encoding="utf-8") as fh:
        fh.write(f"PLATFORM_LIVE_BEARER_TOKEN={token}\n")
        fh.write(f"PLATFORM_LIVE_ORG_ID={org_id}\n")
        fh.write(f"PLATFORM_LIVE_AUTH_MODE={AUTH_MODE}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--github-env", action="store_true", help="export to $GITHUB_ENV (masked)"
    )
    args = parser.parse_args()
    env = {k: v for k, v in os.environ.items() if v}
    from supabase import create_client

    client = create_client(
        _required(env, "SUPABASE_URL"), _required(env, "SUPABASE_SERVICE_ROLE_KEY")
    )
    token, org_id = mint_session(env, client)
    if args.github_env:
        target = os.environ.get("GITHUB_ENV")
        if not target:
            raise SmokeSessionError("--github-env needs GITHUB_ENV")
        export_to_github(token, org_id, Path(target))
    print(
        f"minted {AUTH_MODE} session for org {org_id}, expires in {TOKEN_TTL_SECONDS}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
