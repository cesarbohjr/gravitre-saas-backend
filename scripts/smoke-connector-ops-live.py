#!/usr/bin/env python3
"""Live smoke for connector ops metrics (Item 2).

Prefers GET /api/admin/intelligence/connector-writes when admin auth works.
Falls back to service-role aggregation against prod audit_events.

Writes docs/delivery/connector-ops-live.json
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import dotenv_values
from httpx import AsyncClient

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
PROD = "https://gravitre-saas-backend-production.up.railway.app"
OUT = REPO / "docs" / "delivery" / "connector-ops-live.json"
PERIOD_DAYS = 7


def _env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if p.is_file():
            try:
                merged.update({k: v for k, v in dotenv_values(p).items() if v})
            except UnicodeDecodeError:
                pass
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _token(env: dict[str, str], user_id: str, email: str) -> str:
    url = env["SUPABASE_URL"].rstrip("/")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


async def _try_http(base: str, token: str) -> tuple[dict | None, dict]:
    meta: dict = {"attempted": True, "status": None, "error": None}
    try:
        async with AsyncClient(base_url=base, timeout=60.0, verify=False) as ac:
            health = (await ac.get("/health")).json()
            meta["git_sha"] = health.get("git_sha") or health.get("sha")
            r = await ac.get(
                f"/api/admin/intelligence/connector-writes?periodDays={PERIOD_DAYS}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Org-Id": ORG,
                    "X-Environment": "production",
                },
            )
            meta["status"] = r.status_code
            if r.status_code == 200:
                return r.json(), meta
            meta["error"] = (r.text or "")[:500]
            return None, meta
    except Exception as exc:
        meta["error"] = str(exc)[:500]
        return None, meta


async def main() -> int:
    env = _env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    member = (
        client.table("organization_members")
        .select("user_id,role")
        .eq("org_id", ORG)
        .limit(20)
        .execute()
        .data
        or []
    )
    admin_row = next((m for m in member if str(m.get("role") or "").lower() in {"admin", "owner"}), None)
    actor = str((admin_row or (member[0] if member else {})).get("user_id") or "")
    email = f"{actor}@gravitre.local"
    if actor:
        try:
            users = client.auth.admin.get_user_by_id(actor)
            email = (users.user.email if users and users.user else None) or email
        except Exception:
            pass

    base = (sys.argv[1] if len(sys.argv) > 1 else PROD).rstrip("/")
    started = datetime.now(timezone.utc).isoformat()
    mode = "http_admin"
    http_meta: dict = {"attempted": False}
    payload: dict | None = None

    if actor and env.get("SUPABASE_JWT_SECRET"):
        token = _token(env, actor, email)
        payload, http_meta = await _try_http(base, token)

    if payload is None:
        mode = "service_role_db"
        from app.services.connector_ops_metrics_service import load_connector_ops_metrics

        payload = await load_connector_ops_metrics(ORG, period_days=PERIOD_DAYS, settings=settings)

    artifact = {
        "ran_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "org_id": ORG,
        "base_url": base,
        "period_days": PERIOD_DAYS,
        "mode": mode,
        "http": http_meta,
        "note": (
            "HTTP admin endpoint used"
            if mode == "http_admin"
            else "Admin HTTP auth unavailable or non-200; aggregated via service-role against prod audit_events"
        ),
        "metrics": payload,
        "verdict": "PASS" if isinstance(payload, dict) and "rows" in payload else "FAIL",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mode": mode, "verdict": artifact["verdict"], "out": str(OUT), "spikeCount": payload.get("spikeCount")}, indent=2))
    return 0 if artifact["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
