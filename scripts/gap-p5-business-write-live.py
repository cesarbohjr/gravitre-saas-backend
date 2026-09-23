#!/usr/bin/env python3
"""Isolated-org HubSpot WRITE through governed chat confirm — not a noop workflow.

Placeholder contact only. Not a customer catalog action.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))
spec = importlib.util.spec_from_file_location("evc", ROOT / "scripts" / "audit-evidence-closure.py")
evc = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(evc)

OUT = ROOT / "docs" / "audits" / "gravitre-p5-business-write-live.json"
EMAIL_DOMAIN = "gravitre-smoke.example.com"


def main() -> int:
    env = evc.load_env()
    from supabase import create_client

    from app.services.entity_get_verify import extract_entity_id, verify_entity_get
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext
    from app.config import get_settings

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    health = httpx.get(f"{evc.BASE}/health", timeout=45).json()
    iso_org, user_id, email = evc.resolve_isolated_conversation_actor(env, sb)
    token = evc.mint(env, user_id, email)
    headers = {
        **evc.smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "X-Org-Id": iso_org,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    marker = uuid.uuid4().hex[:10]
    probe_email = f"placeholder.isolated.{marker}@{EMAIL_DOMAIN}"
    prompt = (
        f'Create a HubSpot contact for {probe_email} named "Placeholder Isolated Org". '
        "This is a labeled isolated-org operator verification fixture, not a customer action."
    )
    since = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
    out: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health_sha": health.get("git_sha"),
        "org_id": iso_org,
        "fixture_label": "placeholder isolated-org operator verification — not customer catalog",
        "probe_email": probe_email,
        "prompt": prompt,
    }
    with httpx.Client(timeout=180) as client:
        cr = client.post(
            f"{evc.BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"p5-write-{marker}"},
        )
        cr.raise_for_status()
        conv = str(cr.json()["id"])
        out["conversation_id"] = conv
        history: list = []
        first = evc.chat_turn(client, headers, iso_org, conv, history, prompt)
        time.sleep(0.8)
        confirm = evc.chat_turn(client, headers, iso_org, conv, history, "yes")
        time.sleep(2.0)
    out["first"] = {
        "excerpt": (first.get("assistant_excerpt") or "")[:900],
        "http_status": first.get("http_status"),
        "first_ms": first.get("first_useful_text_ms"),
    }
    out["confirm"] = {
        "excerpt": (confirm.get("assistant_excerpt") or "")[:900],
        "http_status": confirm.get("http_status"),
        "first_ms": confirm.get("first_useful_text_ms"),
    }
    audits = evc.audit_since(sb, iso_org, since, 120)
    out["actions"] = [a.get("action") for a in audits[:50]]
    out["invokes"] = [
        {
            "action": a.get("action"),
            "created_at": a.get("created_at"),
            "meta": a.get("meta"),
        }
        for a in audits
        if a.get("action") in {"tool.invoke.completed", "tool.invoke.failed"}
    ][:12]
    out["pending"] = [
        {"action": a.get("action"), "created_at": a.get("created_at")}
        for a in audits
        if "pending" in str(a.get("action") or "").lower()
        or "approval" in str(a.get("action") or "").lower()
    ][:12]
    out["observations"] = [
        {"action": a.get("action"), "created_at": a.get("created_at")}
        for a in audits
        if "observation" in str(a.get("action") or "").lower()
    ][:8]
    settings = get_settings()
    connector_rows = (
        sb.table("connectors")
        .select("id, type, status")
        .eq("org_id", iso_org)
        .eq("type", "hubspot")
        .is_("deleted_at", "null")
        .limit(5)
        .execute()
        .data
        or []
    )
    connector_id = None
    for row in connector_rows:
        if str(row.get("status") or "").lower() in {"active", "connected", "healthy"}:
            connector_id = str(row["id"])
            break
    out["connector_id"] = connector_id
    entity_id = None
    if connector_id:
        ctx = ToolContext(
            settings=settings,
            client=sb,
            org_id=iso_org,
            actor_id=user_id,
            connector_id=connector_id,
        )
        listed = invoke_tool(
            ctx,
            "hubspot.contacts.search",
            {"connector_id": connector_id, "query": probe_email, "limit": 5},
        )
        out["search_after"] = {
            "success": bool(listed.success),
            "error": (listed.error_message or "")[:200] or None,
        }
        payload = listed.data if isinstance(listed.data, dict) else {}
        for row in payload.get("results") or []:
            if not isinstance(row, dict):
                continue
            props = row.get("properties") if isinstance(row.get("properties"), dict) else {}
            if str(props.get("email") or "").lower() == probe_email.lower():
                entity_id = str(row.get("id") or "")
                break
            entity_id = str(row.get("id") or entity_id or "")
        if entity_id:
            verify = verify_entity_get(
                invoke_action="hubspot.contacts.create",
                result_data={"id": entity_id},
                ctx=ctx,
                settle=True,
            )
            out["verify_entity_get"] = verify.as_dict()
            d = invoke_tool(
                ctx,
                "hubspot.contacts.delete",
                {"connector_id": connector_id, "contact_id": entity_id},
            )
            out["cleanup_deleted"] = {
                "success": bool(d.success),
                "error": (d.error_message or "")[:200] or None,
                "contact_id": entity_id,
            }
    out["written_entity_id"] = entity_id
    invoke_ok = any(a.get("action") == "tool.invoke.completed" for a in out["invokes"])
    completed_language = "complet" in (out["confirm"].get("excerpt") or "").lower() or "created" in (
        out["confirm"].get("excerpt") or ""
    ).lower()
    out["chain_ok"] = bool(invoke_ok and entity_id)
    out["completed_language"] = completed_language
    OUT.write_text(json.dumps(out, indent=2, default=str)[:120000] + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, default=str)[:8000])
    return 0 if out["chain_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
