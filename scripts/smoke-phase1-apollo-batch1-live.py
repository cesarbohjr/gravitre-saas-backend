#!/usr/bin/env python3
"""Live smoke: Apollo Batch 1 — people.match + organizations.enrich.

Writes docs/delivery/phase1-apollo-batch1-live.json

Bar: real invoke_tool against smoke-org Apollo connector; result_url or real error.
Does NOT grant chat access (that comes after this evidence + review).
"""
from __future__ import annotations

import json
import os
import sys
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
OUT = REPO / "docs" / "delivery" / "phase1-apollo-batch1-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
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


def _rec(invoke) -> dict:
    data = invoke.data or {}
    return {
        "success": bool(invoke.success),
        "error_code": invoke.error_code,
        "error_message": invoke.error_message,
        "result_url": data.get("result_url"),
        "summary": data.get("summary"),
        "data_keys": list(data.keys())[:12],
    }


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.services.catalog_write_authority import invoke_action_requires_write_approval
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    tip = None
    try:
        tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")
    except Exception as exc:  # noqa: BLE001
        tip = f"health_unreachable:{exc.__class__.__name__}"

    rows = (
        sb.table("connectors")
        .select("id, type, status")
        .eq("org_id", ORG)
        .eq("type", "apollo")
        .is_("deleted_at", "null")
        .limit(5)
        .execute()
    ).data or []
    apollo_id = None
    for row in rows:
        if str(row.get("status") or "").lower() in {"active", "connected", "healthy"}:
            apollo_id = str(row["id"])
            break

    delete_gate_ok = invoke_action_requires_write_approval("apollo.contacts.delete") is True
    remove_gate_ok = invoke_action_requires_write_approval("apollo.sequences.remove") is True

    invokes: dict[str, dict] = {}
    live_ok = False
    if apollo_id:
        ctx = ToolContext(
            settings=settings,
            client=sb,
            org_id=ORG,
            actor_id=ACTOR,
            connector_id=apollo_id,
        )
        match = invoke_tool(
            ctx,
            "apollo.people.match",
            {"connector_id": apollo_id, "email": "tim@apollo.io", "domain": "apollo.io"},
        )
        invokes["apollo.people.match"] = _rec(match)
        live_ok = live_ok or (
            bool(match.success) and bool((match.data or {}).get("result_url"))
        ) or (
            # Plan-limit / auth errors are real evidence — not mocks
            bool(match.error_message)
        )

        enrich = invoke_tool(
            ctx,
            "apollo.organizations.enrich",
            {"connector_id": apollo_id, "domain": "apollo.io"},
        )
        invokes["apollo.organizations.enrich"] = _rec(enrich)
        live_ok = live_ok or (
            bool(enrich.success) and bool((enrich.data or {}).get("result_url"))
        ) or bool(enrich.error_message)

    # Strict PASS: connector present + at least one success with result_url
    success_with_url = any(
        r.get("success") and r.get("result_url") for r in invokes.values()
    )
    passed = bool(apollo_id) and success_with_url and delete_gate_ok and remove_gate_ok

    artifact = {
        "pass": passed,
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "batch": "phase1-apollo-batch1",
        "api_version": "api/v1 (unchanged — no bump)",
        "new_actions": ["apollo.people.match", "apollo.organizations.enrich"],
        "apollo_connector_id": apollo_id,
        "invokes": invokes,
        "governance": {
            "contacts_delete_requires_approval": delete_gate_ok,
            "sequences_remove_requires_approval": remove_gate_ok,
            "finance_hr_excluded": True,
            "chat_access_granted": False,
            "note": "Chat/ReAct/canvas access deferred until this tip PASS is reviewed",
        },
        "note": (
            "Apollo Batch 1: people.match + organizations.enrich with result_url. "
            "Existing create/update/delete already catalogued; delete approval re-confirmed."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "out": str(OUT), "apollo_id": apollo_id, "tip": tip}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
