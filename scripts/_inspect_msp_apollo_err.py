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
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"


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
    aud = (
        sb.table("audit_events")
        .select("action,created_at,metadata")
        .eq("org_id", ORG)
        .gte("created_at", "2026-08-14T10:08:00Z")
        .lte("created_at", "2026-08-14T10:08:40Z")
        .order("created_at")
        .limit(80)
        .execute()
    ).data or []
    out = []
    for a in aud:
        meta = a.get("metadata") or {}
        blob = json.dumps(meta, default=str)
        if RUN in blob or "apollo" in blob.lower() or "step_failed" in blob.lower() or "lists.add" in blob:
            out.append(
                {
                    "at": a.get("created_at"),
                    "action": a.get("action"),
                    "meta": {
                        k: meta.get(k)
                        for k in (
                            "action",
                            "tool",
                            "invoke_action",
                            "error",
                            "error_message",
                            "error_code",
                            "success",
                            "step_id",
                            "run_id",
                            "detail",
                            "message",
                        )
                        if k in meta
                    }
                    or {k: meta.get(k) for k in list(meta)[:12]},
                }
            )
    print(json.dumps(out, indent=2, default=str))
    # people search entity_ids size from step output
    peep = (
        sb.table("workflow_steps")
        .select("output_snapshot")
        .eq("run_id", RUN)
        .eq("step_id", "apollo_people_search")
        .limit(1)
        .execute()
    ).data or []
    if peep:
        snap = peep[0].get("output_snapshot") or {}
        print(
            "people_search",
            {
                "entity_ids_n": len(snap.get("entity_ids") or [])
                if isinstance(snap.get("entity_ids"), list)
                else None,
                "contact_ids_n": len(snap.get("contact_ids") or [])
                if isinstance(snap.get("contact_ids"), list)
                else None,
                "record_count": snap.get("record_count"),
                "success": snap.get("success"),
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
