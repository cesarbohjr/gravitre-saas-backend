#!/usr/bin/env python3
"""P5 live matrix: two executable workflows + one legitimately blocked. Isolated org only."""
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

ORG = evc.ORG
BASE = evc.BASE
CANVAS_RUN = "cdda7de2-bfbb-4cc7-b490-842fb5e7df84"
OUT = ROOT / "docs" / "audits" / "gravitre-p5-workflow-matrix-live.json"

INTERESTING = (
    "competitive intelligence",
    "uncertain lead",
    "sales automation",
    "f6 prod process",
    "canvas write",
)


def _interesting_score(name: str) -> int:
    lowered = (name or "").lower()
    for i, needle in enumerate(INTERESTING):
        if needle in lowered:
            return i
    return 99


def _run_named(client, headers, iso_org, sb, name: str, since: str) -> dict:
    cr = client.post(
        f"{BASE}/api/conversations",
        headers={k: v for k, v in headers.items() if k != "Accept"},
        json={"title": f"p5-{uuid.uuid4().hex[:6]}"},
    )
    cr.raise_for_status()
    conv = str(cr.json()["id"])
    history: list = []
    prompt = f"Run the workflow named {name} in this conversation now."
    turn = evc.chat_turn(client, headers, iso_org, conv, history, prompt)
    time.sleep(0.8)
    yes = evc.chat_turn(client, headers, iso_org, conv, history, "yes")
    time.sleep(2.5)
    audits = evc.audit_since(sb, iso_org, since, 160)
    actions = [a.get("action") for a in audits]
    return {
        "name": name,
        "conversation_id": conv,
        "prompt": prompt,
        "ask_excerpt": (turn.get("assistant_excerpt") or "")[:600],
        "yes_excerpt": (yes.get("assistant_excerpt") or "")[:800],
        "ask_ms": turn.get("first_useful_text_ms"),
        "yes_ms": yes.get("first_useful_text_ms"),
        "actions": actions[:40],
        "child_obs": [a for a in audits if a.get("action") == "workflow.child.observation"][:6],
        "step_failed": [a for a in audits if a.get("action") == "workflow.execute.step_failed"][:4],
        "execute_failed": [a for a in audits if a.get("action") == "workflow.execute.failed"][:3],
        "pending_approval": [a for a in audits if a.get("action") == "workflow.execute.pending_approval"][:3],
        "execute_completed": [a for a in audits if a.get("action") == "workflow.execute.completed"][:3],
        "composer": [
            a
            for a in audits
            if a.get("action") == "response.composer.completed"
        ][:4],
    }


def main() -> int:
    env = evc.load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    health = httpx.get(f"{BASE}/health", timeout=45).json()
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
    wfs = (
        sb.table("workflows")
        .select("id,name")
        .eq("org_id", iso_org)
        .limit(20)
        .execute()
        .data
        or []
    )
    blocked_rows = (
        sb.table("workflow_runs")
        .select("id,workflow_id,status,approval_status,trigger_type,run_type,created_at,error_message")
        .eq("org_id", iso_org)
        .eq("run_type", "execute")
        .in_("status", ["pending_approval", "running"])
        .execute()
        .data
        or []
    )
    blocked_ids = {str(r.get("workflow_id") or "") for r in blocked_rows if r.get("workflow_id")}
    canvas = (
        sb.table("workflow_runs")
        .select("id,workflow_id,status,approval_status,trigger_type,run_type,created_at,error_message")
        .eq("id", CANVAS_RUN)
        .limit(1)
        .execute()
        .data
        or []
    )
    zero_approval = {
        str(p.get("workflow_id") or "")
        for p in (
            sb.table("approval_policies")
            .select("workflow_id,required_approvals,run_types")
            .eq("org_id", iso_org)
            .eq("required_approvals", 0)
            .execute()
            .data
            or []
        )
        if p.get("workflow_id") and "execute" in (p.get("run_types") or [])
    }
    executable = sorted(
        [w for w in wfs if str(w.get("id") or "") in zero_approval and str(w.get("id") or "") not in blocked_ids],
        key=lambda w: _interesting_score(str(w.get("name") or "")),
    )
    blocked_named = [w for w in wfs if str(w.get("id") or "") in blocked_ids]
    canvas_wf = next((w for w in wfs if "canvas write" in str(w.get("name") or "").lower()), None)

    out: dict = {
        "health_sha": health.get("git_sha"),
        "org_id": iso_org,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "canvas_human_only": {
            "run_id": CANVAS_RUN,
            "row": canvas[0] if canvas else None,
            "required_human_action": "Approve, cancel, or leave pending. Do not auto-approve/cancel/bypass.",
            "mutated": False,
        },
        "blocked_runs": blocked_rows,
        "executable_candidates": [{"id": w.get("id"), "name": w.get("name")} for w in executable[:8]],
    }

    with httpx.Client(timeout=180) as client:
        success_runs = []
        for w in executable[:2]:
            since = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
            success_runs.append(_run_named(client, headers, iso_org, sb, str(w.get("name") or ""), since))
        out["success_attempts"] = success_runs

        blocked_target = canvas_wf or (blocked_named[0] if blocked_named else None)
        if blocked_target:
            since_b = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
            blocked_live = _run_named(client, headers, iso_org, sb, str(blocked_target.get("name") or ""), since_b)
            blocked_live["claimed_complete"] = "done" in (blocked_live.get("yes_excerpt") or "").lower() and "started" in (
                blocked_live.get("yes_excerpt") or ""
            ).lower()
            out["blocked_attempt"] = blocked_live

    OUT.write_text(json.dumps(out, indent=2, default=str)[:120000] + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, default=str)[:8000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
