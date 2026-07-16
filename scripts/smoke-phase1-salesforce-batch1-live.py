#!/usr/bin/env python3
"""Tip salesforce.query (SOQL) against the smoke org Salesforce connector.

Writes docs/delivery/phase1-salesforce-batch1-live.json.
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
OUT = REPO / "docs" / "delivery" / "phase1-salesforce-batch1-live.json"
SOQL = "SELECT Id, Name FROM Account LIMIT 3"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    extra = os.environ.get("GRAVITRE_ENV_DIR")
    candidates = [
        BACKEND / ".env",
        BACKEND / ".env.operator.local",
        REPO / ".env",
    ]
    if extra:
        ep = Path(extra)
        candidates = [ep / ".env", ep / ".env.operator.local", *candidates]
    for p in candidates:
        if not p.is_file():
            continue
        loaded = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if loaded:
            merged.update({k: v for k, v in loaded.items() if v})
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

    conn = get_connector_by_type(sb, ORG, "salesforce", environment_name="production")
    if not conn:
        artifact = {
            "pass": False,
            "status": "BLOCKED_EXTERNAL",
            "ran_at": utcnow(),
            "prod_git_sha": tip,
            "org_id": ORG,
            "batch": "phase1-salesforce-batch1",
            "error": "No active Salesforce connector on smoke org — connect Salesforce in UI then re-run.",
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(artifact, indent=2))
        return 2

    cid = str(conn["id"])
    ctx = ToolContext(
        settings=settings,
        client=sb,
        org_id=ORG,
        actor_id=ACTOR,
        connector_id=cid,
    )
    got = invoke_tool(ctx, "salesforce.query", {"connector_id": cid, "soql": SOQL})
    data = got.data or {}
    artifact = {
        "pass": bool(got.success),
        "status": "PASS" if got.success else "FAIL",
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "batch": "phase1-salesforce-batch1",
        "connector_id": cid,
        "soql": SOQL,
        "invoke": {
            "action": "salesforce.query",
            "success": got.success,
            "error_code": got.error_code,
            "error_message": got.error_message,
            "summary": data.get("summary"),
            "total_size": data.get("total_size"),
        },
        "governance": {
            "chat_access_granted": False,
            "finance_hr_excluded": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0 if got.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
