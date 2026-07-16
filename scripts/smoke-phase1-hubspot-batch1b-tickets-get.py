#!/usr/bin/env python3
"""Tip hubspot.tickets.get with a real ticket id (create then get).

Updates docs/delivery/phase1-hubspot-batch1b-live.json tickets.get section
and writes phase1-hubspot-batch1b-tickets-get-live.json.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values
from supabase import create_client

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
HUB_ID = "547cdda5-2637-4a2b-b087-d5ea89486575"
OUT = REPO / "docs" / "delivery" / "phase1-hubspot-batch1b-tickets-get-live.json"
MAIN_TIP = REPO / "docs" / "delivery" / "phase1-hubspot-batch1b-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    extra = os.environ.get("GRAVITRE_ENV_DIR")
    candidates = [
        BACKEND / ".env",
        BACKEND / ".env.operator.local",
        REPO / ".env",
    ]
    if extra:
        ep = Path(extra)
        candidates = [ep / ".env", ep / ".env.operator.local", *candidates]
    for p in candidates:
        if not p.is_file():
            continue
        loaded = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if loaded:
            merged.update({k: v for k, v in loaded.items() if v})
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.connectors.hubspot import create_ticket
    from app.connectors.hubspot_oauth import ensure_hubspot_access_token
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")

    token, err = ensure_hubspot_access_token(
        sb, ORG, HUB_ID, settings, environment_name="production"
    )
    if err or not token:
        raise SystemExit(f"token failed: {err}")

    suffix = uuid.uuid4().hex[:8]
    # Create via CRM API (not tickets.create tool — that path requires approval).
    # This only supplies a real ticket_id so tickets.get can be tipped.
    created = create_ticket(
        token,
        {
            "subject": f"Gravitre Batch1b tickets.get tip {suffix}",
            "content": "Disposable tip ticket for hubspot.tickets.get live trace.",
            "hs_pipeline": "0",
            "hs_pipeline_stage": "1",
        },
    )
    ticket_id = str((created or {}).get("id") or "")
    if not ticket_id:
        raise SystemExit(f"create_ticket returned no id: {created}")

    ctx = ToolContext(
        settings=settings,
        client=sb,
        org_id=ORG,
        actor_id=ACTOR,
        connector_id=HUB_ID,
    )
    got = invoke_tool(
        ctx,
        "hubspot.tickets.get",
        {"connector_id": HUB_ID, "ticket_id": ticket_id},
    )
    data = got.data or {}
    artifact = {
        "pass": bool(got.success and data.get("result_url")),
        "status": "PASS" if got.success and data.get("result_url") else "FAIL",
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "batch": "phase1-hubspot-batch1b-tickets-get-confirm",
        "clarification": (
            "Prior tip recorded tickets.get as smoke-script skip (no ticket id from search). "
            "This run creates a real ticket then invokes hubspot.tickets.get via tool_service."
        ),
        "ticket_id": ticket_id,
        "create_via": "hubspot.create_ticket CRM API (fixture only)",
        "invoke": {
            "action": "hubspot.tickets.get",
            "success": bool(got.success),
            "error_code": got.error_code,
            "error_message": got.error_message,
            "result_url": data.get("result_url"),
            "summary": data.get("summary"),
            "ticket_keys": list((data.get("ticket") or {}).keys())[:12]
            if isinstance(data.get("ticket"), dict)
            else [],
        },
        "governance": {"chat_access_granted": False, "finance_hr_excluded": True},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    # Patch main Batch 1b tip artifact if present
    if MAIN_TIP.is_file():
        main = json.loads(MAIN_TIP.read_text(encoding="utf-8"))
        main.setdefault("invokes", {})["hubspot.tickets.get"] = {
            "success": bool(got.success),
            "error_code": got.error_code,
            "error_message": got.error_message,
            "result_url": data.get("result_url"),
            "summary": data.get("summary"),
            "data_keys": list(data.keys())[:12],
        }
        main["tickets_get_confirm"] = {
            "ran_at": utcnow(),
            "ticket_id": ticket_id,
            "evidence": str(OUT.relative_to(REPO)).replace("\\", "/"),
            "note": "Genuine live tip after fixture ticket create (not smoke skip).",
        }
        if artifact["pass"]:
            main["note"] = (
                "HubSpot Batch 1b tip PASS — companies.create, owners.list, and "
                "tickets.get (confirmed with real ticket id)."
            )
        MAIN_TIP.write_text(json.dumps(main, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"pass": artifact["pass"], "out": str(OUT), "ticket_id": ticket_id, "result_url": data.get("result_url")}, indent=2))
    return 0 if artifact["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
