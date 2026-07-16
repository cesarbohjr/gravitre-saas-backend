#!/usr/bin/env python3
"""Tip nvd.cve.get + cisa_kev.feed.get on the smoke org via invoke_tool.

Writes docs/delivery/phase1-nvd-cisa-batch1-live.json.
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
OUT = REPO / "docs" / "delivery" / "phase1-nvd-cisa-batch1-live.json"
CVE = "CVE-2024-21762"


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
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")
    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id=ACTOR)

    nvd = invoke_tool(ctx, "nvd.cve.get", {"cve_id": CVE})
    kev = invoke_tool(ctx, "cisa_kev.feed.get", {})

    artifact = {
        "pass": bool(nvd.success and kev.success),
        "status": "PASS" if nvd.success and kev.success else "FAIL",
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "batch": "phase1-nvd-cisa-batch1",
        "invokes": {
            "nvd.cve.get": {
                "success": nvd.success,
                "error_code": nvd.error_code,
                "error_message": nvd.error_message,
                "result_url": (nvd.data or {}).get("result_url"),
                "cve_id": (nvd.data or {}).get("cve_id"),
            },
            "cisa_kev.feed.get": {
                "success": kev.success,
                "error_code": kev.error_code,
                "error_message": kev.error_message,
                "count": (kev.data or {}).get("count"),
            },
        },
        "governance": {
            "chat_access_granted": False,
            "finance_hr_excluded": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0 if artifact["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
