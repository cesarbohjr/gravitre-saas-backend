"""Production smoke: unified marketplace assets browse API."""
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
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")


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


def _request(path: str, token: str, org_id: str) -> dict:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", "production")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def main() -> int:
    env = _load_env()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if env.get(key) and not os.environ.get(key):
            os.environ[key] = env[key]

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
    print(f"using org_id={org_id}")

    assets = _request("/api/marketplace/assets?limit=5&environment=production", token, org_id)
    asset_list = assets.get("assets") or []
    total = assets.get("total")
    print(f"assets: {len(asset_list)} returned, total={total}")
    if int(total or 0) < 20:
        print("expected seeded catalog with 20+ assets", file=sys.stderr)
        return 1

    categories = _request("/api/marketplace/categories?environment=production", token, org_id)
    print(f"categories: {len(categories.get('categories') or [])}")

    summary = _request("/api/marketplace/analytics/summary?environment=production", token, org_id)
    print(f"analytics summary keys: {sorted(summary.keys())}")

    slug = asset_list[0].get("slug") if asset_list else None
    if slug:
        detail = _request(f"/api/marketplace/assets/{slug}?environment=production", token, org_id)
        title = (detail.get("asset") or {}).get("title")
        print(f"detail: {slug} -> {title}")

    print("OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        raise SystemExit(1) from exc
