#!/usr/bin/env python3
"""Module A original trigger via chat UI execute path (not direct finalize).

Seeds an isolated-org conversation with a pending multi-step orchestration plan
whose first step is a broken webhook, then hits the same confirm/execute API the
AI workspace uses when the user approves a plan. Collects fanout IDs for the
resulting failed run.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("MODULE_A_CHAT_UI_BASE", "https://api.gravitre.app").rstrip("/")


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = (env.get("SUPABASE_JWT_SECRET") or "").strip()
    if not secret:
        raise SystemExit("SUPABASE_JWT_SECRET required to mint chat-UI smoke JWT")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for name in (".env", "backend/.env", "apps/web/.env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    from supabase import create_client

    url, key = env.get("SUPABASE_URL"), env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")

    client = create_client(url, key)
    org_id, user_id, email = resolve_isolated_conversation_actor(env, client)
    started_at = datetime.now(timezone.utc).isoformat()
    conversation_id = str(uuid.uuid4())
    now = started_at

    # Pending orchestration matching chat UI plan-confirm → execute path.
    # Status must be awaiting_plan_confirm (not awaiting_confirm) for orch execute.
    steps = [
        {
            "step_id": "step_1",
            "segment": "post broken webhook",
            "label": "Post broken webhook (intentional fail)",
            "kind": "write",
            "supported": True,
            "requires_approval": False,
            "plan": {
                "tool_name": "webhook_post",
                "invoke_action": "webhook.post",
                "integration": "webhook",
                "kind": "write",
                "label": "Post broken webhook (intentional fail)",
                "args": {"url": "", "method": "POST", "body": {}},
                "requires_approval": False,
                "destructive": False,
            },
        },
    ]
    params = {
        "goal": "Module A chat UI failing orchestration",
        "steps": steps,
        "current_step_index": 0,
        "step_results": [],
        "total_steps": len(steps),
        "kind": "write",
        "hitl_action_kind": "write",
    }
    current_plan = {
        "goal": params["goal"],
        "steps": [
            {
                "step_id": "step_1",
                "description": "Post broken webhook (intentional fail)",
                "requires_approval": False,
                "supported": True,
            }
        ],
    }
    client.table("conversations").upsert(
        {
            "id": conversation_id,
            "org_id": org_id,
            "user_id": user_id,
            "title": "Module A chat-UI fail verify",
            "preview": "chat-ui-fail",
            "message_count": 1,
            "task_state": {
                "current_plan": current_plan,
                "pending_steps": steps,
                "completed_steps": [],
                "clarified_params": params,
                "pending_task": {
                    "type": "connector_orchestration",
                    "status": "awaiting_plan_confirm",
                    "params": params,
                },
            },
            "created_at": now,
            "updated_at": now,
        }
    ).execute()

    token = _mint_token(env, user_id, email)
    hdr = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    execute_status = None
    execute_body: dict | list | str | None = None
    chat_http = None
    chat_raw = ""
    with httpx.Client(base_url=BASE, timeout=180.0, verify=False) as http:
        # Typing "yes" into chat (CONFIRM_PATTERN) — same as approving in the UI.
        chat_resp = http.post(
            "/api/assistant/chat",
            headers={**hdr, "Accept": "text/event-stream"},
            json={
                "messages": [
                    {
                        "role": "user",
                        "parts": [{"type": "text", "text": "yes"}],
                    }
                ],
                "org_id": org_id,
                "mode": "agent",
                "conversation_id": conversation_id,
                "tools": ["connector_status", "execute_workflow"],
            },
        )
        chat_http = chat_resp.status_code
        chat_raw = chat_resp.text[:2000]

        # If chat did not consume the pending plan, hit the confirm-button execute path.
        st_mid = (
            client.table("conversations")
            .select("task_state")
            .eq("id", conversation_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        mid_pending = (
            ((st_mid.data or [{}])[0].get("task_state") or {}).get("pending_task") or {}
        )
        still_waiting = str(mid_pending.get("status") or "") in {
            "awaiting_plan_confirm",
            "awaiting_step_confirm",
            "awaiting_confirm",
        }
        if still_waiting:
            ex = http.post(
                f"/api/assistant/conversation/{conversation_id}/execute",
                headers=hdr,
                json={"confirm": True},
            )
            execute_status = ex.status_code
            try:
                execute_body = ex.json()
            except Exception:
                execute_body = ex.text[:500]
        else:
            execute_status = None
            execute_body = {"skipped": True, "reason": "chat_consumed_pending_plan"}

    # Resolve run_id from conversation state / execute body / recent orch runs
    run_id = None
    if isinstance(execute_body, dict):
        run_id = (
            execute_body.get("run_id")
            or execute_body.get("runId")
            or (execute_body.get("result") or {}).get("entity_id")
        )
    st = (
        client.table("conversations")
        .select("task_state")
        .eq("id", conversation_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    task_state = ((st.data or [{}])[0].get("task_state") or {})
    if not run_id:
        params = (task_state.get("clarified_params") or {}) if isinstance(task_state, dict) else {}
        run_id = params.get("orchestration_run_id") or params.get("run_id")
    if not run_id:
        pending = (task_state.get("pending_task") or {}) if isinstance(task_state, dict) else {}
        pparams = pending.get("params") if isinstance(pending.get("params"), dict) else {}
        run_id = pparams.get("orchestration_run_id") or pparams.get("run_id")
    if not run_id:
        recent = (
            client.table("workflow_runs")
            .select("id,parameters,status,created_at")
            .eq("org_id", org_id)
            .gte("created_at", started_at)
            .order("created_at", desc=True)
            .limit(15)
            .execute()
            .data
            or []
        )
        for row in recent:
            params = row.get("parameters") if isinstance(row.get("parameters"), dict) else {}
            if str(params.get("conversation_id") or "") == conversation_id:
                run_id = str(row["id"])
                break
            if params.get("source") == "chat_orchestration" and row.get("status") == "failed":
                run_id = str(row["id"])
                break

    fanout = {
        "run_id": run_id,
        "run_status_legacy": None,
        "run_status_contract": None,
        "audit_event_ids": [],
        "audit_log_ids": [],
        "notification_ids": [],
        "learning_event_ids": [],
    }
    checks = {
        "chat_or_execute_reached": bool(chat_http or execute_status),
        "run_id_present": bool(run_id),
        "runs_legacy_failed": False,
        "runs_contract_failed": False,
        "audit_events": False,
        "audit_logs": False,
        "notifications_run_failed": False,
        "learning_workflow_failed": False,
    }
    if run_id:
        legacy = (
            client.table("workflow_runs")
            .select("id,status")
            .eq("id", run_id)
            .limit(1)
            .execute()
        )
        fanout["run_status_legacy"] = ((legacy.data or [{}])[0].get("status"))
        checks["runs_legacy_failed"] = fanout["run_status_legacy"] == "failed"
        contract = (
            client.table("runs").select("id,status").eq("id", run_id).limit(1).execute()
        )
        fanout["run_status_contract"] = ((contract.data or [{}])[0].get("status"))
        checks["runs_contract_failed"] = str(fanout["run_status_contract"] or "").lower() == "failed"

        ae = (
            client.table("audit_events")
            .select("id")
            .eq("org_id", org_id)
            .eq("action", "workflow.execute.failed")
            .eq("resource_id", run_id)
            .gte("created_at", started_at)
            .execute()
        )
        fanout["audit_event_ids"] = [r["id"] for r in (ae.data or [])]
        checks["audit_events"] = bool(fanout["audit_event_ids"])

        al = (
            client.table("audit_logs")
            .select("id,resource_id")
            .eq("org_id", org_id)
            .eq("action", "workflow.execute.failed")
            .gte("created_at", started_at)
            .limit(20)
            .execute()
        )
        fanout["audit_log_ids"] = [
            r["id"] for r in (al.data or []) if str(r.get("resource_id")) == run_id
        ]
        checks["audit_logs"] = bool(fanout["audit_log_ids"])

        notes = (
            client.table("notifications")
            .select("id")
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .eq("type", "run_failed")
            .eq("entity_id", run_id)
            .gte("created_at", started_at)
            .execute()
        )
        fanout["notification_ids"] = [r["id"] for r in (notes.data or [])]
        checks["notifications_run_failed"] = bool(fanout["notification_ids"])

        learn = (
            client.table("intelligence_outcome_events")
            .select("id")
            .eq("org_id", org_id)
            .eq("workflow_run_id", run_id)
            .eq("outcome_event", "workflow_failed")
            .gte("created_at", started_at)
            .execute()
        )
        fanout["learning_event_ids"] = [r["id"] for r in (learn.data or [])]
        checks["learning_workflow_failed"] = bool(fanout["learning_event_ids"])

    artifact = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "module": "A",
        "path": "chat_ui_execute",
        "base": BASE,
        "org_id": org_id,
        "user_id": user_id,
        "email": email,
        "conversation_id": conversation_id,
        "chat_http": chat_http,
        "chat_raw_preview": chat_raw,
        "execute_http": execute_status,
        "execute_body_preview": str(execute_body)[:800],
        "fanout": fanout,
        "checks": checks,
        "pass": all(
            checks[k]
            for k in (
                "run_id_present",
                "runs_legacy_failed",
                "runs_contract_failed",
                "audit_events",
                "audit_logs",
                "notifications_run_failed",
                "learning_workflow_failed",
            )
        ),
        "note": (
            "Chat UI path: seeded awaiting_plan_confirm orchestration + POST chat "
            "'yes' (CONFIRM_PATTERN; consumed pending). Execute API used only if "
            "chat left the plan still waiting."
        ),
    }
    out = ROOT / "docs/delivery/module-a-chat-ui-fail-live.json"
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0 if artifact["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
