#!/usr/bin/env python3
"""Live smoke: apollo.lists.create end-to-end against real Apollo API.

Writes docs/delivery/apollo-lists-create-live.json

Bar: invoke_tool succeeds; audit would show tool.invoke.completed; list id in result.
Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY and a healthy Apollo connector
(smoke org cbbf993b… or isolated org f07e57c0…).
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

OUT = REPO / "docs" / "delivery" / "apollo-lists-create-live.json"
ORG = os.environ.get("APOLLO_SMOKE_ORG_ID", "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea")


def _load_env() -> None:
    from dotenv import dotenv_values

    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def main() -> int:
    _load_env()
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        report = {
            "verdict": "NOT RUN",
            "reason": "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY",
            "at": datetime.now(timezone.utc).isoformat(),
        }
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    from types import SimpleNamespace

    from supabase import create_client

    from app.config import get_settings
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    actor_rows = (
        client.table("organization_members")
        .select("user_id")
        .eq("org_id", ORG)
        .limit(1)
        .execute()
        .data
        or []
    )
    actor_id = str(actor_rows[0].get("user_id") or "") if actor_rows else ""
    list_name = f"gravitre-lists-create-smoke-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    run_id = str(uuid.uuid4())

    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=ORG,
        actor_id=actor_id or "00000000-0000-0000-0000-000000000001",
        run_id=run_id,
        environment_name="production",
    )
    started = datetime.now(timezone.utc).isoformat()
    result = invoke_tool(
        ctx,
        "apollo.lists.create",
        {"list_name": list_name, "modality": "contacts"},
    )
    finished = datetime.now(timezone.utc).isoformat()

    audit_rows = (
        client.table("audit_events")
        .select("id, created_at, action, metadata")
        .eq("org_id", ORG)
        .gte("created_at", started)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    invoke_audit = [
        r
        for r in audit_rows
        if str(r.get("action") or "").startswith("tool.invoke")
        and isinstance(r.get("metadata"), dict)
        and (r["metadata"].get("action") == "apollo.lists.create" or r["metadata"].get("tool") == "apollo.lists.create")
    ]

    label = (result.data or {}).get("label") if isinstance(result.data, dict) else {}
    list_id = None
    if isinstance(label, dict):
        list_id = label.get("id") or label.get("_id")

    report = {
        "started_at": started,
        "finished_at": finished,
        "org_id": ORG,
        "run_id": run_id,
        "list_name": list_name,
        "invoke": {
            "success": result.success,
            "error_code": result.error_code,
            "error_message": result.error_message,
            "connector_id": result.connector_id,
            "list_id": list_id,
            "result_url": (result.data or {}).get("result_url") if isinstance(result.data, dict) else None,
        },
        "audit_invoke_events": [
            {
                "id": r.get("id"),
                "created_at": r.get("created_at"),
                "action": r.get("action"),
                "error_code": (r.get("metadata") or {}).get("error_code"),
            }
            for r in invoke_audit
        ],
        "verdict": "PASS" if result.success and list_id else "FAIL",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
