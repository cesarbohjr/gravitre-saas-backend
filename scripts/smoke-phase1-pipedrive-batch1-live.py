#!/usr/bin/env python3
"""Tip pipedrive.deals.list (or pipelines.list) on the smoke org.

Writes docs/delivery/phase1-pipedrive-batch1-live.json.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
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
OUT = REPO / "docs" / "delivery" / "phase1-pipedrive-batch1-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not p.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(p).items() if v})
        except UnicodeDecodeError:
            pass
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.connectors.repository import get_connector_by_type
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")
    conn = get_connector_by_type(sb, ORG, "pipedrive", environment_name="production")
    if not conn:
        artifact = {
            "pass": False,
            "status": "BLOCKED_EXTERNAL",
            "ran_at": utcnow(),
            "prod_git_sha": tip,
            "org_id": ORG,
            "batch": "phase1-pipedrive-batch1",
            "error": "No active Pipedrive connector on smoke org.",
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(artifact, indent=2))
        return 2

    cid = str(conn["id"])
    ctx = ToolContext(
        settings=settings, client=sb, org_id=ORG, actor_id=ACTOR, connector_id=cid
    )
    attempts = []
    for action in ("pipedrive.pipelines.list", "pipedrive.deals.list"):
        got = invoke_tool(ctx, action, {"connector_id": cid})
        attempts.append(
            {
                "action": action,
                "success": got.success,
                "error_code": got.error_code,
                "error_message": got.error_message,
            }
        )
        if got.success:
            artifact = {
                "pass": True,
                "status": "PASS",
                "ran_at": utcnow(),
                "prod_git_sha": tip,
                "org_id": ORG,
                "batch": "phase1-pipedrive-batch1",
                "connector_id": cid,
                "invoke": attempts[-1],
                "attempts": attempts,
            }
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(artifact, indent=2))
            return 0

    artifact = {
        "pass": False,
        "status": "FAIL",
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "batch": "phase1-pipedrive-batch1",
        "connector_id": cid,
        "attempts": attempts,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
