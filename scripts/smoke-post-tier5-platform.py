"""Post–Tier 5 platform smoke: role packs, integration health, suggestions, failure alerts."""
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

    org_id, user_id, email = _admin_org(env)
    token = _mint_token(env, user_id, email)
    print(f"using org_id={org_id} user_id={user_id}")

    steps: list[tuple[str, str, str, dict | None]] = [
        ("role_packs", "GET", "/api/marketplace/role-packs", None),
        ("integration_health", "GET", "/api/enterprise/integration-health?lookbackDays=30", None),
        ("health_snapshot", "POST", "/api/enterprise/integration-health/snapshot?lookbackDays=30", {}),
        (
            "suggestions_scan",
            "POST",
            "/api/enterprise/integration-suggestions/scan?lookbackDays=30",
            {},
        ),
        ("suggestions_open", "GET", "/api/enterprise/integration-suggestions?status=open", None),
        ("failure_predictions", "GET", "/api/workflows/failure-predictions?status=open", None),
        ("health_history", "GET", "/api/enterprise/integration-health/history?limit=5", None),
    ]

    for label, method, path, body in steps:
        print(f"step: {label}")
        try:
            result = _request(method, path, token, org_id, body)
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            print(f"HTTP {exc.code} at step {label}: {err_body}", file=sys.stderr)
            raise SystemExit(1) from exc
        if label == "role_packs":
            packs = result.get("packs") or []
            print(f"  role_packs: {len(packs)} catalog entries")
            if len(packs) < 4:
                raise SystemExit("expected at least 4 department role packs")
        elif label == "integration_health":
            print(
                "  integration_health:",
                json.dumps(
                    {k: result.get(k) for k in ("score", "grade", "lookbackDays")},
                    indent=2,
                ),
            )
            if result.get("score") is None or result.get("grade") not in {
                "healthy",
                "at_risk",
                "critical",
            }:
                raise SystemExit("integration health response invalid")
        elif label == "health_snapshot":
            snap = result.get("snapshot") or {}
            print(f"  health_snapshot: score={snap.get('score')} grade={snap.get('grade')}")
        elif label == "suggestions_scan":
            print(f"  integration_suggestions_scan: count={result.get('suggestionCount')}")
        elif label == "suggestions_open":
            print(f"  integration_suggestions_open: count={result.get('count')}")
        elif label == "failure_predictions":
            print(f"  failure_predictions_open: count={result.get('count')}")
        elif label == "health_history":
            print(f"  health_history: count={result.get('count')}")

    print("OK")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        raise SystemExit(1) from exc
