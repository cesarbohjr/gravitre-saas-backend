"""Smoke Tier 5 vertical packs against production (legal install + execute, real-estate install)."""
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
ENV_FILE = REPO / "backend" / ".env.operator.local"
ENV_BACKEND = REPO / "backend" / ".env"
API_BASE = os.environ.get(
    "BACKEND_URL",
    "https://api.gravitre.app",
).rstrip("/")


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (ENV_BACKEND, ENV_FILE):
        if path.is_file():
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
    return merged


def _request(method: str, path: str, token: str, org_id: str, body: dict | None = None) -> dict:
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment=production"
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", "production")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET") or os.environ.get("SUPABASE_JWT_SECRET", "")
    supabase_url = (env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")).rstrip("/")
    if not secret or not supabase_url:
        raise SystemExit("SUPABASE_JWT_SECRET and SUPABASE_URL required in backend/.env.operator.local")
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


def _admin_org(env: dict[str, str]) -> tuple[str, str, str]:
    from supabase import create_client

    url = env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    client = create_client(url, key)
    members = (
        client.table("organization_members")
        .select("org_id, user_id, role")
        .eq("role", "admin")
        .limit(1)
        .execute()
    )
    if not members.data:
        raise SystemExit("No admin organization_members row found")
    row = members.data[0]
    org_id = str(row["org_id"])
    user_id = str(row["user_id"])
    users = client.auth.admin.get_user_by_id(user_id)
    email = (users.user.email if users and users.user else None) or f"{user_id}@gravitre.local"
    return org_id, user_id, email


def main() -> None:
    env = _load_env()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if env.get(key) and not os.environ.get(key):
            os.environ[key] = env[key]

    # Clio status (no auth)
    clio_url = f"{API_BASE}/api/connectors/oauth/clio/status"
    with urllib.request.urlopen(clio_url, timeout=30) as resp:
        clio = json.loads(resp.read().decode("utf-8"))
    print("clio_status:", json.dumps(clio, indent=2))
    if not clio.get("configured"):
        raise SystemExit("Clio OAuth not configured on production")

    org_id, user_id, email = _admin_org(env)
    token = _mint_token(env, user_id, email)
    print(f"using org_id={org_id} user_id={user_id}")

    legal = _request("POST", "/api/verticals/legal/install", token, org_id, {})
    print("legal_install:", json.dumps(legal, indent=2))
    workflow_id = legal.get("intakeWorkflowId")
    if not workflow_id:
        raise SystemExit("legal install missing intakeWorkflowId")

    try:
        execute = _request(
            "POST",
            "/api/workflows/execute",
            token,
            org_id,
            {"workflow_id": workflow_id, "parameters": {}},
        )
        print(
            "legal_execute:",
            json.dumps({k: execute.get(k) for k in ("run_id", "status", "queued", "errors")}, indent=2),
        )
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            body = exc.read().decode("utf-8", errors="replace")
            print("legal_execute: skipped (workflow already has an active run)")
            print(body)
        else:
            raise

    re_install = _request("POST", "/api/verticals/real-estate/install", token, org_id, {})
    print("real_estate_install:", json.dumps(re_install, indent=2))
    print("OK")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        raise SystemExit(1) from exc
