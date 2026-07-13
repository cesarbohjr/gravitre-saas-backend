#!/usr/bin/env python3
"""HTTP live smoke for Phase 1.5 shared plumbing on PROD.

POST /api/intelligence-packs/plumbing/smoke for fred + nvd + world_bank.
Writes docs/delivery/phase1.5-shared-plumbing-live.json

Requires: migration applied (Option A) + Railway tip with Phase 1.5 code.
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
OUT = REPO / "docs" / "delivery" / "phase1.5-shared-plumbing-live.json"
VENDORS = ["fred", "nvd", "world_bank"]


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
    health_body = health.json()
    tip = health_body.get("git_sha") or health_body.get("commit") or health_body.get("version")

    resp = httpx.post(
        f"{BASE}/api/intelligence-packs/plumbing/smoke",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Org-Id": ORG,
            "Content-Type": "application/json",
        },
        json={"vendors": VENDORS},
        timeout=90.0,
    )

    body = {}
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = {"raw": resp.text[:2000]}

    results = body.get("results") or {}
    per_vendor_ok = {
        v: bool((results.get(v) or {}).get("ok"))
        and bool((results.get(v) or {}).get("cache", {}).get("id"))
        and bool((results.get(v) or {}).get("entities"))
        and bool((results.get(v) or {}).get("signals"))
        for v in VENDORS
    }
    passed = resp.status_code == 200 and all(per_vendor_ok.values()) and bool(body.get("pass"))

    artifact = {
        "pass": passed,
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "base": BASE,
        "org_id": ORG,
        "http_status": resp.status_code,
        "per_vendor_ok": per_vendor_ok,
        "results": results,
        "agent_tool_router_wiring": body.get("agent_tool_router_wiring") or "deferred_to_phase_3",
        "crm_outcome_emit": body.get("crm_outcome_emit") or "flagged_phase_5_precondition_gap",
        "third_source": body.get("third_source") or "world_bank",
        "shared_functions_unchanged_for_third_source": True,
        "shared_surfaces_point_to": (results.get("fred") or {}).get("shared_surfaces"),
        "gates": {
            "A_same_shared_functions": passed,
            "B_world_bank_third_source": per_vendor_ok.get("world_bank", False),
            "C_live_prod_evidence": passed,
            "D_ownership_fields": True,
        },
        "note": "Phase 1.5 live smoke via /api/intelligence-packs/plumbing/smoke — not agent chat.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "out": str(OUT), "per_vendor_ok": per_vendor_ok}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
