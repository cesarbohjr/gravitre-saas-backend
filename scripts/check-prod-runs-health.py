"""Quick authenticated prod check for STA-275: /health and GET /api/runs."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import jwt

REPO = Path(__file__).resolve().parent.parent
OPERATOR_ENV = REPO / "backend" / ".env.operator.local"
API_BASE = "https://api.gravitre.app"


def load_operator_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for path in (REPO / "backend" / ".env", OPERATOR_ENV):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"')
            if value:
                env[key.strip()] = value
    return env


def main() -> int:
    env = load_operator_env()
    if not env.get("SUPABASE_URL") or not env.get("SUPABASE_SERVICE_ROLE_KEY") or not env.get("SUPABASE_JWT_SECRET"):
        print("Missing SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, or SUPABASE_JWT_SECRET in backend/.env or .env.operator.local")
        return 1

    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    row = (
        client.table("organization_members")
        .select("org_id,user_id,role")
        .eq("role", "admin")
        .limit(1)
        .execute()
        .data[0]
    )
    org_id = str(row["org_id"])
    user_id = str(row["user_id"])
    user = client.auth.admin.get_user_by_id(user_id).user
    email = user.email if user and user.email else f"{user_id}@gravitre.local"
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )

    failed = 0
    health_req = urllib.request.Request(f"{API_BASE}/health", method="GET")
    with urllib.request.urlopen(health_req, timeout=30) as resp:
        health = json.loads(resp.read().decode("utf-8"))
        print(f"PASS /health -> {resp.status} version={health.get('version')} ai_disabled={health.get('ai_disabled')}")

    runs_req = urllib.request.Request(f"{API_BASE}/api/runs?limit=10&environment=production", method="GET")
    runs_req.add_header("Authorization", f"Bearer {token}")
    runs_req.add_header("X-Org-Id", org_id)
    runs_req.add_header("X-Environment", "production")
    try:
        with urllib.request.urlopen(runs_req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(
                f"PASS /api/runs -> {resp.status} "
                f"runs={len(data.get('runs') or [])} total={data.get('total')}"
            )
    except urllib.error.HTTPError as exc:
        failed += 1
        body = exc.read().decode("utf-8", errors="replace")[:400]
        print(f"FAIL /api/runs -> {exc.code} {body}")

    return failed


if __name__ == "__main__":
    raise SystemExit(main())
