#!/usr/bin/env python3
"""HMAC / PendingAction / Sales Automation second-workflow live probes. Isolated org."""
from __future__ import annotations

import importlib.util
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys_path_setup = ROOT
import sys

sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))
spec = importlib.util.spec_from_file_location("evc", ROOT / "scripts" / "audit-evidence-closure.py")
evc = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(evc)

OUT = ROOT / "docs" / "audits" / "gravitre-remaining-matrix-live.json"


def _turn(client, headers, iso_org, sb, prompt: str, yes: str | None = None) -> dict:
    cr = client.post(
        f"{evc.BASE}/api/conversations",
        headers={k: v for k, v in headers.items() if k != "Accept"},
        json={"title": f"mx-{uuid.uuid4().hex[:6]}"},
    )
    cr.raise_for_status()
    conv = str(cr.json()["id"])
    history: list = []
    since = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
    turn = evc.chat_turn(client, headers, iso_org, conv, history, prompt)
    yes_turn = None
    if yes:
        time.sleep(0.6)
        yes_turn = evc.chat_turn(client, headers, iso_org, conv, history, yes)
        time.sleep(1.5)
    else:
        time.sleep(0.8)
    audits = evc.audit_since(sb, iso_org, since, 80)
    return {
        "prompt": prompt,
        "conversation_id": conv,
        "excerpt": (turn.get("assistant_excerpt") or "")[:700],
        "first_ms": turn.get("first_useful_text_ms"),
        "yes_excerpt": ((yes_turn or {}).get("assistant_excerpt") or "")[:700] if yes_turn else None,
        "actions": [a.get("action") for a in audits[:36]],
        "invokes": [a for a in audits if a.get("action") in {"tool.invoke.completed", "tool.invoke.failed"}][:6],
        "child_obs": [a for a in audits if a.get("action") == "workflow.child.observation"][:4],
        "pending": [a for a in audits if "pending" in str(a.get("action") or "")][:6],
    }


def main() -> int:
    env = evc.load_env()
    from supabase import create_client

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
    out = {"health_sha": health.get("git_sha"), "org_id": iso_org, "generated_at": datetime.now(timezone.utc).isoformat()}
    with httpx.Client(timeout=180) as client:
        out["hmac_or_pending_write"] = _turn(client, headers, iso_org, sb, "Send Sarah a summary.")
        out["sales_automation"] = _turn(
            client,
            headers,
            iso_org,
            sb,
            "Run the workflow named Sales Automation in this conversation now.",
            yes="yes",
        )
        out["uncertain_lead"] = _turn(
            client,
            headers,
            iso_org,
            sb,
            "Run the workflow named Uncertain lead in this conversation now.",
            yes="yes",
        )
    OUT.write_text(json.dumps(out, indent=2, default=str)[:100000] + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, default=str)[:7000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
