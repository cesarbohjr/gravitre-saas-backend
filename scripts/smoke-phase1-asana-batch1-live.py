#!/usr/bin/env python3
"""Tip a read Asana action on the smoke org (workspaces/projects list if available).

Writes docs/delivery/phase1-asana-batch1-live.json.
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
OUT = REPO / "docs" / "delivery" / "phase1-asana-batch1-live.json"

# Prefer registered read actions in order.
CANDIDATE_ACTIONS = (
    "asana.workspaces.list",
    "asana.projects.list",
    "asana.tasks.search",
    "asana.users.me",
)


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
    from app.services.asana_tools import ASANA_TOOL_EXECUTORS
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")

    conn = get_connector_by_type(sb, ORG, "asana", environment_name="production")
    if not conn:
        artifact = {
            "pass": False,
            "status": "BLOCKED_EXTERNAL",
            "ran_at": utcnow(),
            "prod_git_sha": tip,
            "org_id": ORG,
            "batch": "phase1-asana-batch1",
            "error": "No active Asana connector on smoke org — connect Asana in UI then re-run.",
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

    registered = [a for a in CANDIDATE_ACTIONS if a in ASANA_TOOL_EXECUTORS]
    if not registered:
        registered = sorted(
            a
            for a in ASANA_TOOL_EXECUTORS
            if any(tok in a for tok in (".list", ".get", ".me", ".search"))
        )

    attempts = []
    for action in registered[:4]:
        got = invoke_tool(ctx, action, {"connector_id": cid})
        attempts.append(
            {
                "action": action,
                "success": got.success,
                "error_code": got.error_code,
                "error_message": got.error_message,
                "summary": (got.data or {}).get("summary") if got.data else None,
            }
        )
        if got.success:
            artifact = {
                "pass": True,
                "status": "PASS",
                "ran_at": utcnow(),
                "prod_git_sha": tip,
                "org_id": ORG,
                "batch": "phase1-asana-batch1",
                "connector_id": cid,
                "invoke": attempts[-1],
                "attempts": attempts,
                "governance": {
                    "chat_access_granted": False,
                    "finance_hr_excluded": True,
                },
            }
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(artifact, indent=2))
            return 0

    artifact = {
        "pass": False,
        "status": "FAIL" if registered else "BLOCKED_INTERNAL",
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "batch": "phase1-asana-batch1",
        "connector_id": cid,
        "attempts": attempts,
        "error": "No successful Asana read tip" if registered else "No asana.* executors registered",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
