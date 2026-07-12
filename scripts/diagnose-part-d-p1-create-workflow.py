"""Diagnose Part D P1 create_workflow prod failure (conversation 53b3b342...)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

for path in (BACKEND / ".env", BACKEND / ".env.operator.local", ROOT / ".env.operator.local", ROOT / ".env"):
    if not path.is_file():
        continue
    try:
        for k, v in dotenv_values(path).items():
            if v:
                os.environ.setdefault(k, v)
    except Exception:
        pass

from app.config import get_settings
from app.services.assistant_tools import tool_create_workflow
from app.workflows.repository import get_supabase_client

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
CONV = "53b3b342-8246-4223-8fe8-20088f360461"
SINCE = "2026-07-12T02:30:00Z"
BASE = "https://gravitre-saas-backend-production.up.railway.app"


def main() -> None:
    settings = get_settings()
    client = get_supabase_client(settings)
    print("=== settings ok ===")
    print(f"supabase_url={settings.supabase_url[:48]}...")

    print("\n=== audit_events (recent matching) ===")
    rows = (
        client.table("audit_events")
        .select("id,action,resource_type,resource_id,metadata,created_at,actor_id")
        .eq("org_id", ORG)
        .gte("created_at", SINCE)
        .order("created_at", desc=True)
        .limit(80)
        .execute()
        .data
        or []
    )
    matched = []
    for r in rows:
        action = str(r.get("action") or "")
        meta = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
        meta_action = str(meta.get("action") or "")
        if (
            meta_action == "assistant.create_workflow"
            or action.startswith("tool.invoke.")
            or action == "workflow.created"
        ):
            matched.append(r)
    for r in matched[:20]:
        print(json.dumps(r, default=str))
    print(f"matched_count={len(matched)} printed={min(20, len(matched))}")

    print("\n=== workflow_defs recent 5 ===")
    try:
        wfs = (
            client.table("workflow_defs")
            .select("id,name,status,stage,goal,schema_version,version,created_at,updated_at,created_by")
            .eq("org_id", ORG)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print(f"extended select failed: {exc}")
        wfs = (
            client.table("workflow_defs")
            .select("id,name,status,schema_version,version,created_at,updated_at,created_by")
            .eq("org_id", ORG)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
            .data
            or []
        )
    for w in wfs:
        print(json.dumps(w, default=str))

    print("\n=== PartD name hits ===")
    name_hits = (
        client.table("workflow_defs")
        .select("id,name,status,schema_version,created_at")
        .eq("org_id", ORG)
        .ilike("name", "%PartD P1%")
        .order("created_at", desc=True)
        .limit(10)
        .execute()
        .data
        or []
    )
    for h in name_hits:
        print(json.dumps(h, default=str))

    print("\n=== tool_create_workflow local call (unique) ===")
    actor = os.environ.get("OAUTH_SMOKE_USER_ID")
    if not actor:
        actor = (
            client.table("organization_members")
            .select("user_id")
            .eq("org_id", ORG)
            .limit(1)
            .execute()
            .data[0]["user_id"]
        )
    unique_goal = f"PartD P1 diag create {uuid.uuid4().hex[:8]} {datetime.now(timezone.utc).isoformat()}"
    print(f"actor={actor}")
    print(f"goal={unique_goal}")
    try:
        out = tool_create_workflow(ORG, unique_goal, settings, user_id=actor)
        print("return=", json.dumps(out, default=str, indent=2))
    except Exception:
        traceback.print_exc()

    print("\n=== tool_create_workflow same name as live failure ===")
    live_goal = "PartD P1 live gate create verification 2026-07-12"
    try:
        out2 = tool_create_workflow(ORG, live_goal, settings, user_id=actor)
        print("return=", json.dumps(out2, default=str, indent=2))
    except Exception:
        traceback.print_exc()

    print("\n=== prod health ===")
    try:
        import urllib.request

        with urllib.request.urlopen(f"{BASE}/health", timeout=20) as resp:
            print(f"status={resp.status} body={resp.read().decode('utf-8', errors='replace')[:500]}")
    except Exception as exc:
        print(f"health failed: {exc}")

    print("\n=== railway CLI ===")
    if shutil.which("railway"):
        try:
            r = subprocess.run(
                ["railway", "logs", "--lines", "200"],
                capture_output=True,
                text=True,
                timeout=45,
                cwd=str(ROOT),
            )
            combined = (r.stdout or "") + "\n" + (r.stderr or "")
            print(f"railway_exit={r.returncode}")
            hits = [
                ln
                for ln in combined.splitlines()
                if "create_workflow" in ln.lower() or "assistant create_workflow" in ln.lower()
            ]
            print(f"log_hits={len(hits)}")
            for ln in hits[-30:]:
                print(ln)
            if not hits:
                for ln in combined.splitlines()[-20:]:
                    print(ln)
        except Exception as exc:
            print(f"railway logs failed: {exc}")
    else:
        print("railway CLI not available")


if __name__ == "__main__":
    main()
