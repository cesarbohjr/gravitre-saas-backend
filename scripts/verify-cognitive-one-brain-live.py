#!/usr/bin/env python3
"""Live proof: remaining One Brain LIVE PENDING claims via ops smoke.

Primary path: POST /api/internal/ops/cognitive-one-brain-smoke
Writes docs/delivery/one-brain-live-residuals.json

Usage:
  python scripts/verify-cognitive-one-brain-live.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO / "scripts"))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
OUT = REPO / "docs" / "delivery" / "one-brain-live-residuals.json"
ISOLATED_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
FOREIGN_ORG = "658c76b3-04b7-489b-bb7e-64a5f3ec1cbe"
DEFAULT_ACTOR = "a9f1240f-910a-42ca-aebf-38caeac288c3"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            pass
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _health() -> dict:
    try:
        return httpx.get(f"{BASE}/health", timeout=60.0).json()
    except Exception as exc:  # noqa: BLE001
        return {"git_sha": None, "error": f"{exc.__class__.__name__}:{exc}"}


def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    secret = (env.get("INTERNAL_API_SECRET") or "").strip()
    org_id = (env.get("ISOLATED_CONVERSATION_TEST_ORG_ID") or ISOLATED_ORG).strip()
    actor_id = (
        env.get("ISOLATED_CONVERSATION_TEST_USER_ID")
        or env.get("OAUTH_SMOKE_USER_ID")
        or DEFAULT_ACTOR
    ).strip()
    health = _health()
    tip = health.get("git_sha")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "health_git_sha": tip,
        "org_id": org_id,
        "actor_id": actor_id,
    }

    if not secret:
        payload["verdict"] = "FAIL"
        payload["error"] = "INTERNAL_API_SECRET missing"
        OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 1

    try:
        resp = httpx.post(
            f"{BASE}/api/internal/ops/cognitive-one-brain-smoke",
            headers={"X-Internal-Secret": secret},
            json={
                "org_id": org_id,
                "actor_id": actor_id,
                "foreign_org_id": FOREIGN_ORG,
                "environment_name": "production",
            },
            timeout=240.0,
        )
    except Exception as exc:  # noqa: BLE001
        payload["verdict"] = "FAIL"
        payload["error"] = f"http_error:{exc.__class__.__name__}"
        OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 1

    if resp.status_code == 404:
        payload["verdict"] = "LIVE PENDING"
        payload["error"] = "endpoint_not_deployed"
        OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 2

    if resp.status_code >= 400:
        payload["verdict"] = "FAIL"
        payload["error"] = f"http_{resp.status_code}:{resp.text[:400]}"
        OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 1

    body = resp.json()
    payload["smoke"] = body
    payload["verdict"] = body.get("verdict") or ("PASS" if body.get("pass") else "PARTIAL")
    payload["claim"] = body.get("claim")
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if body.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
