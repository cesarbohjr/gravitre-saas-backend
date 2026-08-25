#!/usr/bin/env python3
"""Inspect Clay connector config shape (no secrets printed)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
CLAY_ID = "17a942d4-d5cf-44da-9ad2-c0bdb4faf729"


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
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext
    from supabase import create_client

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = (
        sb.table("connectors")
        .select("id,status,connector_type,config,updated_at")
        .eq("id", CLAY_ID)
        .limit(1)
        .execute()
    ).data or []
    if not row:
        print("missing connector")
        return 1
    cfg = row[0].get("config") if isinstance(row[0].get("config"), dict) else {}
    # redact
    safe = {}
    for k, v in cfg.items():
        lk = str(k).lower()
        if any(x in lk for x in ("key", "secret", "token", "password", "auth")):
            safe[k] = f"<redacted len={len(str(v))}>"
        elif "url" in lk or "webhook" in lk:
            try:
                u = urlparse(str(v))
                safe[k] = {
                    "scheme": u.scheme,
                    "host": u.hostname,
                    "path_prefix": "/".join((u.path or "").split("/")[:3]),
                    "has_query": bool(u.query),
                }
            except Exception:
                safe[k] = "<unparseable>"
        else:
            safe[k] = v if not isinstance(v, (dict, list)) else type(v).__name__
    print(json.dumps({"status": row[0].get("status"), "connector_type": row[0].get("connector_type"), "updated_at": row[0].get("updated_at"), "config": safe}, indent=2))

    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id="f7e32f06-49df-4e73-8962-f41c21850762")
    # Probe tables.list via invoke (may fail on windows socket)
    r = invoke_tool(ctx, "clay.tables.list", {"connector_id": CLAY_ID})
    print("tables.list", r.success, r.error_code, (r.error_message or "")[:200])
    if r.success and isinstance(r.data, dict):
        tables = r.data.get("tables") or []
        print("tables_n", len(tables) if isinstance(tables, list) else None)
        if isinstance(tables, list) and tables:
            t0 = tables[0] if isinstance(tables[0], dict) else {}
            wh = str(t0.get("webhook_url") or "")
            u = urlparse(wh) if wh else None
            print("table0", {"id": t0.get("id"), "name": t0.get("name"), "webhook_host": u.hostname if u else None})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
