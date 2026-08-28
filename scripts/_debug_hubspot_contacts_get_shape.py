#!/usr/bin/env python3
"""Why did the live entity_get read return no entity?

The adapter guesses the id parameter by convention and pulls the id out of the
response by convention. Either could be wrong for a real vendor. Creates one
disposable contact, calls hubspot.contacts.get with each candidate parameter
name, and prints the raw response shape.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding="utf-8")

ORG = os.environ.get("F6_ORG_ID", "f07e57c0-1501-4000-8000-c04e57a00001")
ACTOR = os.environ.get("F6_ACTOR_ID", "a9f1240f-910a-42ca-aebf-38caeac288c3")


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in (dotenv_values(p, encoding=enc) or {}).items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def main() -> int:
    _load_env()
    from supabase import create_client

    from app.config import get_settings
    from app.services.entity_get_verify import extract_entity_id, id_param_candidates
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    rows = (
        sb.table("connectors")
        .select("id, status")
        .eq("org_id", ORG)
        .eq("type", "hubspot")
        .is_("deleted_at", "null")
        .limit(5)
        .execute()
    ).data or []
    cid = next(
        (str(r["id"]) for r in rows if str(r.get("status") or "").lower() in {"active", "connected", "healthy"}),
        None,
    )
    print("connector:", cid)
    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id=ACTOR, connector_id=cid)

    marker = uuid.uuid4().hex[:12]
    w = invoke_tool(
        ctx,
        "hubspot.contacts.create",
        {
            "connector_id": cid,
            "properties": {
                "email": f"f6.dbg.{marker}@gravitre-smoke.example.com",
                "firstname": "F6",
                "lastname": f"Debug {marker}",
            },
        },
    )
    print("write.success:", w.success)
    data = w.data if isinstance(w.data, dict) else {}
    print("write.data keys:", sorted(data.keys()))
    print("write.data:", json.dumps(data, default=str)[:900])
    eid = extract_entity_id(data, "id")
    print("extracted id:", eid)

    print("\ncandidates:", id_param_candidates("hubspot.contacts.get"))
    for param in id_param_candidates("hubspot.contacts.get"):
        try:
            r = invoke_tool(ctx, "hubspot.contacts.get", {"connector_id": cid, param: eid})
            rd = r.data if isinstance(r.data, dict) else {}
            print(f"\n  param={param!r} success={r.success} err={r.error_code} "
                  f"msg={(r.error_message or '')[:160]}")
            print(f"    data keys: {sorted(rd.keys())}")
            print(f"    data: {json.dumps(rd, default=str)[:700]}")
            print(f"    extract_entity_id -> {extract_entity_id(rd, 'id')}")
        except Exception as exc:  # noqa: BLE001
            print(f"  param={param!r} raised {exc.__class__.__name__}: {exc}")

    if eid:
        d = invoke_tool(ctx, "hubspot.contacts.delete", {"connector_id": cid, "contact_id": eid})
        print("\ncleanup deleted:", d.success)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
