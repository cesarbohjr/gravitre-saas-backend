#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
RUN = os.environ.get("STUCK_RUN_ID", "cd970041-a1c6-497a-8140-cc116225558c")


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
        .select("id,status,error_message,completed_at,approval_status")
        .eq("id", RUN)
        .limit(1)
        .execute()
    ).data[0]
    steps = (
        sb.table("workflow_steps")
        .select("step_id,status,error_message,error_code,output_snapshot")
        .eq("run_id", RUN)
        .order("step_index")
        .execute()
    ).data or []
    print(json.dumps({"run": run, "steps": [
        {
            "step_id": s.get("step_id"),
            "status": s.get("status"),
            "error_code": s.get("error_code"),
            "error": (s.get("error_message") or "")[:800] or None,
            "output_keys": list((s.get("output_snapshot") or {}).keys())[:20]
            if isinstance(s.get("output_snapshot"), dict)
            else None,
            "output_preview": json.dumps(s.get("output_snapshot"), default=str)[:1200]
            if s.get("step_id") == "apollo_list_add"
            else None,
        }
        for s in steps
    ]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
