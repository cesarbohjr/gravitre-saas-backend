#!/usr/bin/env python3
"""Hit live ops-summary API on deployed tip + confirm health SHA."""
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("MODULE_A_OPS_BASE", "https://api.gravitre.app").rstrip("/")


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for name in (".env", "backend/.env", "apps/web/.env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, client)
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
    hdr = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "Accept": "application/json",
    }
    with httpx.Client(base_url=BASE, timeout=60.0, verify=False) as http:
        health = http.get("/health").json()
        ops = http.get("/api/workflows/execution-outcomes/ops-summary", headers=hdr)
        try:
            body = ops.json()
        except Exception:
            body = {"raw": ops.text[:500]}
    artifact = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "health_git_sha": health.get("git_sha"),
        "expected_sha_prefix": "bc4c133d",
        "sha_match": str(health.get("git_sha") or "").startswith("bc4c133d"),
        "ops_http": ops.status_code,
        "ops_summary": body,
        "pass": bool(
            str(health.get("git_sha") or "").startswith("bc4c133d")
            and ops.status_code == 200
            and isinstance(body, dict)
            and "by_source" in body
            and "by_connector" in body
        ),
    }
    out = ROOT / "docs/delivery/module-a-ops-summary-live.json"
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0 if artifact["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
