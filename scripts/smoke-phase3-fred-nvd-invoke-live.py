#!/usr/bin/env python3
"""Phase 3 HTTP live smoke: POST /api/intelligence-packs/tools/invoke-smoke on PROD.

Writes docs/delivery/phase3-fred-nvd-invoke-live.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values
from supabase import create_client

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
OUT = REPO / "docs" / "delivery" / "phase3-fred-nvd-invoke-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if p.is_file():
            try:
                merged.update({k: v for k, v in dotenv_values(p).items() if v})
            except UnicodeDecodeError:
                pass
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def _mint_jwt(client) -> str:
    email = client.auth.admin.get_user_by_id(ACTOR).user.email
    url = os.environ["SUPABASE_URL"].rstrip("/")
    secret = os.environ["SUPABASE_JWT_SECRET"]
    now = int(time.time())
    return jwt.encode(
        {
            "sub": ACTOR,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def main() -> int:
    _load_env()
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    token = _mint_jwt(sb)

    health = httpx.get(f"{BASE}/health", timeout=30.0)
    health.raise_for_status()
    tip = (health.json() or {}).get("git_sha")

    resp = httpx.post(
        f"{BASE}/api/intelligence-packs/tools/invoke-smoke",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Org-Id": ORG,
            "Content-Type": "application/json",
        },
        json={"fred_series_id": "GDP", "nvd_cve_id": "CVE-2024-21762"},
        timeout=90.0,
    )
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = {"raw": resp.text[:2000]}

    results = body.get("results") or {}
    per_ok = body.get("per_action_ok") or {}
    passed = resp.status_code == 200 and bool(body.get("pass")) and all(
        per_ok.get(a) for a in ("fred.series.get", "nvd.cve.get")
    )

    artifact = {
        "pass": passed,
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "base": BASE,
        "org_id": ORG,
        "http_status": resp.status_code,
        "mode": "http_invoke_tool_smoke",
        "per_action_ok": per_ok,
        "results": results,
        "registered": body.get("registered"),
        "agent_tool_router_wiring": body.get("agent_tool_router_wiring") or "phase_3_invoke_tool",
        "note": "Phase 3 HTTP invoke_tool smoke on deployed tip.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "out": str(OUT), "per_action_ok": per_ok, "prod_git_sha": tip}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
