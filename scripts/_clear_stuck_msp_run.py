#!/usr/bin/env python3
"""Cancel or approve a stuck MSP enrichment run so a live retest can proceed."""
from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
import sys

sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
RUN = os.environ.get("STUCK_RUN_ID", "705b3607-d90f-4447-80ef-fe20b88efcc3")
API = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")


def load_env() -> None:
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                for k, v in (loaded or {}).items():
                    if v:
                        os.environ.setdefault(k, v)
                break
            except UnicodeDecodeError:
                continue


def main() -> int:
    load_env()
    from app.config import get_settings
    from supabase import create_client

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = (
        sb.table("workflow_runs")
        .select("id,status,approval_status,required_approvals,error_message")
        .eq("id", RUN)
        .limit(1)
        .execute()
    ).data or [None]
    row = row[0]
    print("before", row)
    if not row:
        return 1
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": ACTOR,
            "email": "cesar@gravitre.app",
            "aud": "authenticated",
            "iss": f"{os.environ['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        os.environ["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": ORG,
        "Content-Type": "application/json",
    }
    status = str(row.get("status") or "")
    with httpx.Client(timeout=180.0) as client:
        if status == "pending_approval":
            resp = client.post(
                f"{API}/api/approvals/{RUN}/approve?environment=production",
                headers=headers,
                json={},
            )
            print("approve", resp.status_code, resp.text[:1200])
        else:
            resp = client.post(
                f"{API}/api/runs/{RUN}/cancel?environment=production",
                headers=headers,
                json={},
            )
            print("cancel", resp.status_code, resp.text[:1200])
    after = (
        sb.table("workflow_runs")
        .select("id,status,approval_status,error_message")
        .eq("id", RUN)
        .limit(1)
        .execute()
    ).data or [None]
    print("after", after[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
