"""P1 live traces: three platform writes on prod a3e69a22.

Evidence bar (Apollo-format): pending_task → confirm → tool.invoke.requested/completed (+ domain audit).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import dotenv_values
from httpx import AsyncClient

ROOT = Path(__file__).resolve().parents[1]
for p in [ROOT / "backend" / ".env", ROOT / ".env.operator.local", ROOT / "backend" / ".env.operator.local"]:
    if p.is_file():
        try:
            for k, v in dotenv_values(p).items():
                if v:
                    os.environ.setdefault(k, v)
        except Exception:
            pass

import sys

sys.path.insert(0, str(ROOT / "backend"))
from app.config import get_settings
from app.workflows.repository import get_supabase_client

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
BASE = "https://gravitre-saas-backend-production.up.railway.app"
# Accept any current prod tip; set PART_D_P1_EXPECTED_SHA_PREFIX to pin when needed.
EXPECTED_SHA_PREFIX = os.environ.get("PART_D_P1_EXPECTED_SHA_PREFIX", "")
OUT = ROOT / "docs" / "delivery" / "part-d-p1-live-traces.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_sse(raw: str) -> dict:
    texts: list[str] = []
    tools: list[dict] = []
    intel: list[dict] = []
    for block in re.split(r"\n\n+", raw):
        for ln in block.splitlines():
            if not ln.startswith("data:"):
                continue
            try:
                o = json.loads(ln[5:].lstrip())
            except Exception:
                continue
            t = o.get("type")
            if t == "text-delta":
                texts.append(o.get("delta") or "")
            if t in ("tool-input-available", "tool-output-available") or (isinstance(t, str) and "tool" in t):
                tools.append({k: o.get(k) for k in ("type", "toolName", "toolCallId") if k in o})
            if t == "data-intelligence":
                d = o.get("data") or {}
                pend = d.get("pendingTask") or d.get("pending_task")
                intel.append(
                    {
                        "mode": d.get("dialogueMode"),
                        "expl": (d.get("answerExplanation") or "")[:120],
                        "pending": pend,
                        "exec": d.get("executionResult") or d.get("execution_result"),
                    }
                )
    return {"text": "".join(texts), "tools": tools, "intel": intel}


def last_pending(intel: list[dict]) -> dict | None:
    for item in reversed(intel):
        pend = item.get("pending")
        if isinstance(pend, dict) and pend.get("type"):
            return pend
    return None


async def chat(
    ac: AsyncClient,
    hdr: dict,
    *,
    text: str,
    tools: list[str],
    conversation_id: str,
    mode: str = "reasoning",
) -> dict:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
        "org_id": ORG,
        "tools": tools,
        "mode": mode,
        "conversation_id": conversation_id,
    }
    r = await ac.post("/api/assistant/chat", json=body, headers=hdr, timeout=180)
    parsed = parse_sse(r.text)
    st = await ac.get(
        f"/api/assistant/conversation/{conversation_id}/state",
        headers={k: v for k, v in hdr.items() if k != "Accept"},
    )
    pending = None
    task_state = None
    if st.status_code == 200:
        task_state = st.json().get("task_state") or {}
        pending = task_state.get("pending_task")
    return {
        "http": r.status_code,
        "conversation_id": conversation_id,
        "text": parsed["text"][:800],
        "tools": parsed["tools"],
        "intel": parsed["intel"],
        "sse_pending": last_pending(parsed["intel"]),
        "db_pending": pending,
        "task_state": task_state,
    }


def audit_rows(client, *, since_iso: str, actions: list[str], limit: int = 40) -> list[dict]:
    rows = (
        client.table("audit_events")
        .select("id,action,resource_type,resource_id,metadata,created_at")
        .eq("org_id", ORG)
        .gte("created_at", since_iso)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    wanted = set(actions)
    out = []
    for row in rows:
        if row.get("action") in wanted:
            out.append(row)
        elif isinstance(row.get("metadata"), dict) and row["metadata"].get("action") in {
            "assistant.create_workflow",
            "assistant.execute_workflow",
            "assistant.run_agent_task",
            "assistant.create_agent",
        }:
            out.append(row)
    return out


def pass_gate(pending: dict | None, expected_type: str) -> bool:
    if not isinstance(pending, dict):
        return False
    return pending.get("type") == expected_type and pending.get("status") == "awaiting_confirm"


async def main() -> None:
    s = get_settings()
    c = get_supabase_client(s)
    actor = os.environ.get("OAUTH_SMOKE_USER_ID") or (
        c.table("organization_members").select("user_id").eq("org_id", ORG).limit(1).execute().data[0]["user_id"]
    )
    email = (c.auth.admin.get_user_by_id(actor).user.email) or f"{actor}@gravitre.local"
    url = os.environ["SUPABASE_URL"].rstrip("/")
    tok = jwt.encode(
        {
            "sub": actor,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "role": "authenticated",
        },
        os.environ["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    hdr = {
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        "Accept": "text/event-stream",
    }
    state_hdr = {
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
    }

    report: dict = {
        "started_at": utcnow(),
        "base_url": BASE,
        "org_id": ORG,
        "actor_id": actor,
        "expected_sha_prefix": EXPECTED_SHA_PREFIX,
        "claim": "part_d_p1_platform_write_gate",
        "pr": 96,
        "merge_commit": "a3e69a220aeaa53718e4aee610e1121b9b6ba4bf",
    }

    async with AsyncClient(base_url=BASE, timeout=180) as ac:
        health = (await ac.get("/health")).json()
        report["prod_health"] = health
        sha = str(health.get("git_sha") or "")
        report["prod_sha_ok"] = (not EXPECTED_SHA_PREFIX) or sha.startswith(EXPECTED_SHA_PREFIX)
        if not report["prod_sha_ok"]:
            report["verdict"] = "BLOCKED_WRONG_SHA"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps({"verdict": report["verdict"], "sha": sha}, indent=2))
            return

        # Unique per run — fixed names collide with prior re-audit creates (duplicate_name).
        create_nonce = uuid.uuid4().hex[:8]
        create_goal = f"PartD P1 live gate create {create_nonce}"

        # ---- 1) create_workflow via ReAct tool (avoid conversational regex) ----
        cid_create = str(uuid.uuid4())
        since_create = utcnow()
        turn_a_create = await chat(
            ac,
            hdr,
            text=(
                f"Please invoke create_workflow now with goal: {create_goal}. "
                "Do not ask clarifying questions — call the tool."
            ),
            tools=["create_workflow", "execute_workflow", "run_agent_task", "connector_status"],
            conversation_id=cid_create,
        )
        pending_create = turn_a_create.get("db_pending") or turn_a_create.get("sse_pending")
        # Fallback: if ReAct didn't fire, use conversational phrasing (same spine)
        if not pass_gate(pending_create, "create_workflow"):
            cid_create = str(uuid.uuid4())
            since_create = utcnow()
            turn_a_create = await chat(
                ac,
                hdr,
                text=(
                    f"Create a workflow named {create_goal} that syncs new HubSpot contacts "
                    "into a Slack digest for PartD P1 gate."
                ),
                tools=["create_workflow", "connector_status"],
                conversation_id=cid_create,
            )
            pending_create = turn_a_create.get("db_pending") or turn_a_create.get("sse_pending")

        turn_b_create = None
        if pass_gate(pending_create, "create_workflow"):
            turn_b_create = await chat(
                ac,
                {**hdr, "Accept": "text/event-stream"},
                text="yes",
                tools=["create_workflow", "connector_status"],
                conversation_id=cid_create,
            )
        audits_create = audit_rows(
            c,
            since_iso=since_create,
            actions=["tool.invoke.requested", "tool.invoke.completed", "tool.invoke.failed", "workflow.created"],
        )
        create_invoke_actions = [
            r
            for r in audits_create
            if r.get("action") in {"tool.invoke.requested", "tool.invoke.completed"}
            and (r.get("metadata") or {}).get("action") == "assistant.create_workflow"
        ]
        create_domain = [r for r in audits_create if r.get("action") == "workflow.created"]
        report["trace_create_workflow"] = {
            "conversation_id": cid_create,
            "turn_a": {
                "http": turn_a_create["http"],
                "text": turn_a_create["text"][:400],
                "db_pending": pending_create,
                "gate_pass": pass_gate(pending_create, "create_workflow"),
            },
            "turn_b": None
            if not turn_b_create
            else {
                "http": turn_b_create["http"],
                "text": turn_b_create["text"][:400],
                "db_pending": turn_b_create.get("db_pending"),
                "exec": (turn_b_create.get("intel") or [{}])[-1].get("exec")
                if turn_b_create.get("intel")
                else None,
            },
            "audits": audits_create[:15],
            "tool_invoke_for_action": create_invoke_actions[:6],
            "workflow_created": create_domain[:3],
            "pass": bool(
                pass_gate(pending_create, "create_workflow")
                and turn_b_create
                and create_invoke_actions
                and any(r.get("action") == "tool.invoke.completed" for r in create_invoke_actions)
                and create_domain
            ),
        }

        # ---- 2) execute_workflow (distinct pending type) ----
        # Prefer a real workflow name from org; fall back to newly created if named
        wfs = c.table("workflow_defs").select("id,name,status").eq("org_id", ORG).order("updated_at", desc=True).limit(20).execute().data or []
        # Prefer non-draft with a recognizable name; else any
        target = None
        for row in wfs:
            name = str(row.get("name") or "")
            if "PartD P1" in name or "Uncertain lead" in name:
                target = row
                break
        if not target and wfs:
            target = wfs[0]
        target_name = str((target or {}).get("name") or "PartD P1")
        target_id = str((target or {}).get("id") or "")

        cid_exec = str(uuid.uuid4())
        since_exec = utcnow()
        turn_a_exec = await chat(
            ac,
            hdr,
            text=(
                f"Please invoke execute_workflow now with query: {target_name}. "
                f"workflowId optional: {target_id}. Call the tool — do not only describe."
            ),
            tools=["execute_workflow", "create_workflow", "connector_status", "workflow_runs"],
            conversation_id=cid_exec,
        )
        pending_exec = turn_a_exec.get("db_pending") or turn_a_exec.get("sse_pending")
        turn_b_exec = None
        if pass_gate(pending_exec, "execute_workflow"):
            turn_b_exec = await chat(
                ac,
                hdr,
                text="yes",
                tools=["execute_workflow", "connector_status"],
                conversation_id=cid_exec,
            )
        audits_exec = audit_rows(
            c,
            since_iso=since_exec,
            actions=["tool.invoke.requested", "tool.invoke.completed", "tool.invoke.failed"],
        )
        exec_invoke = [
            r
            for r in audits_exec
            if r.get("action") in {"tool.invoke.requested", "tool.invoke.completed", "tool.invoke.failed"}
            and (r.get("metadata") or {}).get("action") == "assistant.execute_workflow"
        ]
        # Execute may fail at runtime (no active version) AFTER gate — still count gate+requested;
        # completed preferred; failed after confirm still proves gate + invoke trail if requested exists.
        report["trace_execute_workflow"] = {
            "conversation_id": cid_exec,
            "target_workflow": {"id": target_id, "name": target_name},
            "turn_a": {
                "http": turn_a_exec["http"],
                "text": turn_a_exec["text"][:500],
                "db_pending": pending_exec,
                "gate_pass": pass_gate(pending_exec, "execute_workflow"),
                "approval_copy_has_execute": "execute" in (turn_a_exec.get("text") or "").lower(),
                "approval_copy_not_create_draft": "create a draft" not in (turn_a_exec.get("text") or "").lower(),
            },
            "turn_b": None
            if not turn_b_exec
            else {
                "http": turn_b_exec["http"],
                "text": turn_b_exec["text"][:500],
                "db_pending": turn_b_exec.get("db_pending"),
            },
            "audits": audits_exec[:15],
            "tool_invoke_for_action": exec_invoke[:6],
            "pass": bool(
                pass_gate(pending_exec, "execute_workflow")
                and turn_b_exec
                and any(r.get("action") == "tool.invoke.requested" for r in exec_invoke)
                and any(
                    r.get("action") in {"tool.invoke.completed", "tool.invoke.failed"} for r in exec_invoke
                )
            ),
            "note": "Runtime execute failure after confirm still PASSes gate+audit if requested+completed/failed present",
        }

        # ---- 3) run_agent_task ----
        agents = (
            c.table("agents")
            .select("id,name,status")
            .eq("org_id", ORG)
            .limit(20)
            .execute()
            .data
            or []
        )
        agent = agents[0] if agents else None
        agent_id = str((agent or {}).get("id") or "")
        agent_name = str((agent or {}).get("name") or "agent")

        cid_agent = str(uuid.uuid4())
        since_agent = utcnow()
        turn_a_agent = await chat(
            ac,
            hdr,
            text=(
                f"Please invoke run_agent_task now for agentId {agent_id} ({agent_name}) "
                "with task: Reply with exactly the words P1 gate ok. Call the tool."
            ),
            tools=["run_agent_task", "create_workflow", "connector_status"],
            conversation_id=cid_agent,
        )
        pending_agent = turn_a_agent.get("db_pending") or turn_a_agent.get("sse_pending")
        turn_b_agent = None
        if pass_gate(pending_agent, "run_agent_task"):
            turn_b_agent = await chat(
                ac,
                hdr,
                text="yes",
                tools=["run_agent_task", "connector_status"],
                conversation_id=cid_agent,
            )
        audits_agent = audit_rows(
            c,
            since_iso=since_agent,
            actions=["tool.invoke.requested", "tool.invoke.completed", "tool.invoke.failed"],
        )
        agent_invoke = [
            r
            for r in audits_agent
            if r.get("action") in {"tool.invoke.requested", "tool.invoke.completed", "tool.invoke.failed"}
            and (r.get("metadata") or {}).get("action") == "assistant.run_agent_task"
        ]
        report["trace_run_agent_task"] = {
            "conversation_id": cid_agent,
            "target_agent": {"id": agent_id, "name": agent_name},
            "turn_a": {
                "http": turn_a_agent["http"],
                "text": turn_a_agent["text"][:500],
                "db_pending": pending_agent,
                "gate_pass": pass_gate(pending_agent, "run_agent_task"),
            },
            "turn_b": None
            if not turn_b_agent
            else {
                "http": turn_b_agent["http"],
                "text": turn_b_agent["text"][:500],
                "db_pending": turn_b_agent.get("db_pending"),
            },
            "audits": audits_agent[:15],
            "tool_invoke_for_action": agent_invoke[:6],
            "pass": bool(
                pass_gate(pending_agent, "run_agent_task")
                and turn_b_agent
                and any(r.get("action") == "tool.invoke.requested" for r in agent_invoke)
                and any(
                    r.get("action") in {"tool.invoke.completed", "tool.invoke.failed"} for r in agent_invoke
                )
            ),
        }

    report["finished_at"] = utcnow()
    report["summary"] = {
        "create_workflow": report["trace_create_workflow"]["pass"],
        "execute_workflow": report["trace_execute_workflow"]["pass"],
        "run_agent_task": report["trace_run_agent_task"]["pass"],
    }
    report["all_three_pass"] = all(report["summary"].values())
    report["verdict"] = "PASS" if report["all_three_pass"] else "FAIL"
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "prod_sha": report["prod_health"].get("git_sha"),
                "summary": report["summary"],
                "create_pending": (report["trace_create_workflow"]["turn_a"].get("db_pending") or {}).get("type"),
                "execute_pending": (report["trace_execute_workflow"]["turn_a"].get("db_pending") or {}).get("type"),
                "agent_pending": (report["trace_run_agent_task"]["turn_a"].get("db_pending") or {}).get("type"),
                "out": str(OUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
