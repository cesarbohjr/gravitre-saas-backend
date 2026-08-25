#!/usr/bin/env python3
"""Inspect a workflow run + steps for MSP live retest debugging."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
RUN = os.environ.get("STUCK_RUN_ID", "94c1199f-3b61-45a1-b080-f3716baeab5e")


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
    run = (
        sb.table("workflow_runs")
        .select("*")
        .eq("id", RUN)
        .limit(1)
        .execute()
    ).data or [None]
    steps = (
        sb.table("workflow_steps")
        .select("step_index,step_id,step_name,step_type,status,error_message,started_at,completed_at")
        .eq("run_id", RUN)
        .eq("org_id", ORG)
        .order("step_index")
        .limit(40)
        .execute()
    ).data or []
    print(json.dumps({"run": run[0], "steps": steps}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
