"""Scratch: dump a workflow run's status/error/steps. Disposable diagnostic."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding="utf-8")

for p in (BACKEND / ".env", BACKEND / ".env.operator.local"):
    if not p.is_file():
        continue
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            for k, v in (dotenv_values(p, encoding=enc) or {}).items():
                if v:
                    os.environ.setdefault(k, v)
            break
        except UnicodeDecodeError:
            continue

from app.config import get_settings  # noqa: E402
from supabase import create_client  # noqa: E402

run_id = sys.argv[1]
s = get_settings()
sb = create_client(s.supabase_url, s.supabase_service_role_key)

run = sb.table("workflow_runs").select("*").eq("id", run_id).execute().data
print("RUN:", json.dumps(run, indent=2, default=str)[:3000])

for table in ("workflow_steps", "run_steps"):
    try:
        rows = sb.table(table).select("*").eq("run_id", run_id).execute().data
        if rows:
            print("TABLE", table)
            print(json.dumps(rows, indent=2, default=str)[:4000])
            break
    except Exception as exc:  # noqa: BLE001
        print(table, "ERR", exc)
