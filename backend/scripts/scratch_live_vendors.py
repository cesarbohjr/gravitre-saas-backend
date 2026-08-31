from __future__ import annotations

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

s = get_settings()
sb = create_client(s.supabase_url, s.supabase_service_role_key)

rows = (
    sb.table("connectors")
    .select("org_id,type,status,id")
    .is_("deleted_at", "null")
    .limit(1000)
    .execute()
).data or []

by_status: dict[str, list] = {}
for r in rows:
    by_status.setdefault(str(r.get("status") or "?").lower(), []).append(r)

for status, items in sorted(by_status.items()):
    print(f"\n{status}  ({len(items)})")
    for r in sorted(items, key=lambda x: str(x.get("type"))):
        print(f"   {str(r.get('type')):22s} org={r.get('org_id')} id={r.get('id')}")
