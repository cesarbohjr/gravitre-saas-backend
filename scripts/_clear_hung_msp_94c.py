#!/usr/bin/env python3
"""Clear hung MSP run 94c1199f (false completed + stuck agent step)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

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
    sb.table("workflow_steps").update(
        {
            "status": "failed",
            "error_message": "cleared: hung prepare_clay_batch after F6 false-completed + unresolved agent_seed",
        }
    ).eq("run_id", RUN).eq("step_id", "prepare_clay_batch").execute()
    # failed is valid; avoid invalid transitions on weird completed-without-completed_at rows
    try:
        sb.table("workflow_runs").update(
            {
                "status": "failed",
                "error_message": "cleared for F6 mid-run stamp + agent_seed retest",
            }
        ).eq("id", RUN).execute()
    except Exception as exc:  # noqa: BLE001
        print("run_update_err", exc)
        sb.table("workflow_runs").update(
            {
                "status": "cancelled",
                "error_message": "cleared for F6 mid-run stamp + agent_seed retest",
            }
        ).eq("id", RUN).execute()
    row = (
        sb.table("workflow_runs")
        .select("id,status,error_message,completed_at")
        .eq("id", RUN)
        .limit(1)
        .execute()
    ).data
    print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
