#!/usr/bin/env python3
"""Live re-run: FAST run-history honesty + Module B stale-plan sequence.

Writes docs/delivery/run-history-stale-plan-live.json with evidence pointers.
Uses the isolated conversation test org only (never operator workspace).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import jwt
from dotenv import dotenv_values
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "run-history-stale-plan-live.json"
CHAT_TIMEOUT = 300.0
EXPECT_SHA = os.environ.get("EXPECT_SHA", "481f9862")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    for key in list(os.environ.keys()):
        if key.startswith("SUPABASE_") and "test.supabase" in (os.environ.get(key) or ""):
            os.environ.pop(key, None)
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if merged.get(k):
            os.environ[k] = merged[k]
    return merged


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    tools: list[dict[str, Any]] = []
    intel: list[dict[str, Any]] = []
    for block in re.split(r"\n\n+", raw):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            o = json.loads(payload)
        except json.JSONDecodeError:
            continue
        t = o.get("type")
        if t == "text-delta":
            texts.append(str(o.get("delta") or ""))
        if isinstance(t, str) and "tool" in t:
            tools.append(
                {
                    k: o.get(k)
                    for k in ("type", "toolName", "toolCallId", "input", "output")
                    if k in o
                }
            )
        if t == "data-intelligence":
            d = o.get("data") or {}
            intel.append(
                {
                    "effectiveMode": d.get("effectiveMode"),
                    "answerExplanation": (d.get("answerExplanation") or "")[:400],
                    "pendingTask": d.get("pendingTask") or d.get("pending_task"),
                    "routing": d.get("routing"),
                }
            )
    return {"text": "".join(texts), "tools": tools, "intel": intel}


async def chat_turn(
    ac: httpx.AsyncClient,
    hdr: dict[str, str],
    *,
    text: str,
    conversation_id: str,
    org_id: str,
    mode: str,
    tools: list[str] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
        "org_id": org_id,
        "mode": mode,
        "conversation_id": conversation_id,
    }
    if tools is not None:
        body["tools"] = tools
    chunks: list[bytes] = []
    status = 0
    error = None
    try:
        async with ac.stream(
            "POST",
            "/api/assistant/chat",
            json=body,
            headers=hdr,
            timeout=CHAT_TIMEOUT,
        ) as r:
            status = r.status_code
            async for part in r.aiter_bytes():
                chunks.append(part)
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    parsed = parse_sse(raw)
    task_state = None
    try:
        st = await ac.get(
            f"/api/assistant/conversation/{conversation_id}/state",
            headers={k: v for k, v in hdr.items() if k != "Accept"},
            timeout=60.0,
        )
        if st.status_code == 200:
            payload = st.json()
            task_state = payload.get("task_state") or payload
    except Exception as exc:  # noqa: BLE001
        task_state = {"state_error": str(exc)}
    return {
        "http": status,
        "error": error,
        "user": text,
        "assistant": (parsed["text"] or "")[:2000],
        "tools": parsed["tools"][:20],
        "intel": parsed["intel"][-3:],
        "task_state": task_state,
        "at": utcnow(),
    }


def _tool_names(turn: dict[str, Any]) -> list[str]:
    return [str(row.get("toolName") or "") for row in (turn.get("tools") or []) if row.get("toolName")]


def judge_run_history(turn: dict[str, Any]) -> dict[str, Any]:
    text = (turn.get("assistant") or "").lower()
    names = [n.lower() for n in _tool_names(turn)]
    fabricated = bool(
        re.search(r"\b0\s+recent\s+runs?\b", text)
        or re.search(r"\bno\s+recent\s+runs?\b", text)
    )
    refused = "don't have that information" in text or "do not have that information" in text
    used_runs = any(
        "workflow_run" in n or n.endswith("workflow_runs") or "getworkflowruns" in n
        for n in names
    )
    mode = None
    expl = ""
    for block in turn.get("intel") or []:
        mode = block.get("effectiveMode") or mode
        expl = str(block.get("answerExplanation") or expl)
    if used_runs and not fabricated:
        verdict = "PASS"
        why = "workflow_runs tool used; no fabricated zero-run claim"
    elif refused and not fabricated:
        verdict = "PASS"
        why = "honesty refusal without fabricated run count"
    elif fabricated:
        verdict = "FAIL"
        why = "fabricated recent-run count still present"
    else:
        verdict = "INCONCLUSIVE"
        why = "no fabricated zero, but neither refusal nor workflow_runs evidence"
    return {
        "verdict": verdict,
        "why": why,
        "fabricatedZeroRuns": fabricated,
        "refused": refused,
        "usedWorkflowRunsTool": used_runs,
        "toolNames": names,
        "effectiveMode": mode,
        "explanationSnippet": expl[:300],
    }


def judge_stale_plan(*, unrelated: dict[str, Any], yes_turn: dict[str, Any]) -> dict[str, Any]:
    yes_text = (yes_turn.get("assistant") or "").lower()
    unrelated_text = (unrelated.get("assistant") or "").lower()
    yes_state = yes_turn.get("task_state") if isinstance(yes_turn.get("task_state"), dict) else {}
    pending = yes_state.get("pending_task") if isinstance(yes_state.get("pending_task"), dict) else {}
    plan = yes_state.get("current_plan") if isinstance(yes_state.get("current_plan"), dict) else {}
    plan_goal = str(plan.get("goal") or "").lower()
    reminder_on_unrelated = bool(
        re.search(r"reply\s+\*?\*?yes\*?\*?\s+to\s+approve", unrelated_text)
    )
    yes_tools = " ".join(_tool_names(yes_turn)).lower()
    hubspot_on_yes = "hubspot" in yes_tools
    pending_status = str(pending.get("status") or "")
    old_hubspot_plan_alive = "hubspot" in plan_goal and "slack" in plan_goal
    # A fresh strategic plan for the unrelated question is OK; the old HubSpot
    # orch plan / awaiting gate / hubspot re-invoke on bare "yes" is not.
    ok = (
        not reminder_on_unrelated
        and not hubspot_on_yes
        and pending_status not in {"awaiting_plan_confirm", "awaiting_step_confirm"}
        and not old_hubspot_plan_alive
        and "search contacts" not in yes_text
    )
    return {
        "verdict": "PASS" if ok else "FAIL",
        "reminderOnUnrelated": reminder_on_unrelated,
        "hubspotToolOnYes": hubspot_on_yes,
        "pendingStatusAfterYes": pending_status or None,
        "oldHubspotPlanAlive": old_hubspot_plan_alive,
        "currentPlanGoalAfterYes": plan.get("goal"),
        "unrelatedAssistantSnippet": (unrelated.get("assistant") or "")[:400],
        "yesAssistantSnippet": (yes_turn.get("assistant") or "")[:400],
    }


def seed_sticky_completed_plan(sb: Any, *, conversation_id: str, org_id: str, user_id: str) -> None:
    """Reproduce Module B sticky state: completed orch + leftover current_plan."""
    sticky = {
        "clarified_params": {
            "goal": "Search HubSpot for high-intent leads and draft a follow-up in Slack",
            "steps": [
                {"id": "step_1", "label": "Search contacts", "integration": "hubspot"},
                {"id": "step_2", "label": "Draft Slack follow-up", "integration": "slack"},
            ],
            "step_results": [
                {"success": True, "label": "Search contacts", "summary": "0 contacts"},
            ],
            "current_step_index": 1,
            "total_steps": 2,
        },
        "pending_task": {
            "type": "connector_orchestration",
            "status": "completed",
            "result": {"success": True, "title": "Orchestration complete"},
        },
        "current_plan": {
            "goal": "Search HubSpot for high-intent leads and draft a follow-up in Slack",
            "steps": [
                {"label": "Search contacts"},
                {"label": "Draft Slack follow-up"},
            ],
        },
        "pending_steps": [],
        "completed_steps": ["step_1"],
    }
    existing = (
        sb.table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        sb.table("conversations").update({"task_state": sticky}).eq("id", conversation_id).eq(
            "org_id", org_id
        ).execute()
    else:
        sb.table("conversations").insert(
            {
                "id": conversation_id,
                "org_id": org_id,
                "user_id": user_id,
                "title": "stale-plan-live-verify",
                "task_state": sticky,
            }
        ).execute()


async def wait_for_tip(ac: httpx.AsyncClient, expect: str, minutes: int = 15) -> str:
    deadline = time.time() + minutes * 60
    tip = ""
    while time.time() < deadline:
        try:
            r = await ac.get("/health", timeout=30.0)
            data = r.json() if r.status_code == 200 else {}
            tip = str(data.get("git_sha") or data.get("gitSha") or "")
            print(f"health tip={tip}", flush=True)
            if tip.startswith(expect):
                return tip
        except Exception as exc:  # noqa: BLE001
            print(f"health wait: {exc}", flush=True)
        await asyncio.sleep(20)
    return tip


async def main() -> int:
    env = load_env()
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    url = env["SUPABASE_URL"].rstrip("/")
    tok = jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 7200,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    hdr = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }

    artifact: dict[str, Any] = {
        "checkedAt": utcnow(),
        "apiBase": BASE,
        "orgId": org_id,
        "actor": email,
        "expectSha": EXPECT_SHA,
        "fixCommit": "481f9862",
        "repros": {},
    }

    async with httpx.AsyncClient(base_url=BASE, timeout=CHAT_TIMEOUT) as ac:
        tip = await wait_for_tip(ac, EXPECT_SHA)
        artifact["tipShaObserved"] = tip
        if not tip.startswith(EXPECT_SHA):
            artifact["overall"] = {
                "fastRunHistory": "NOT RUN",
                "stalePlanSequence": "NOT RUN",
                "reason": f"tip {tip} does not include {EXPECT_SHA}",
            }
            OUT.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
            print(json.dumps(artifact["overall"], indent=2))
            return 4

        fast_tools = ["knowledge_base", "agent_status", "connector_status"]

        # --- Repro 1: FAST run-history ---
        conv1 = str(uuid.uuid4())
        t1 = await chat_turn(
            ac,
            hdr,
            text="What workflows have been ran?",
            conversation_id=conv1,
            org_id=org_id,
            mode="fast",
            tools=fast_tools,
        )
        j1 = judge_run_history(t1)
        artifact["repros"]["fastRunHistory"] = {
            "conversationId": conv1,
            "turn": {
                "http": t1["http"],
                "assistant": t1["assistant"][:800],
                "tools": t1["tools"],
                "intel": t1["intel"],
                "at": t1["at"],
                "error": t1.get("error"),
            },
            "judgment": j1,
        }

        # --- Repro 2: seed sticky completed+plan → unrelated → yes ---
        conv2 = str(uuid.uuid4())
        # Create conversation row via a noop-ish first turn, then overwrite state.
        bootstrap = await chat_turn(
            ac,
            hdr,
            text="ping for conversation create",
            conversation_id=conv2,
            org_id=org_id,
            mode="fast",
            tools=fast_tools,
        )
        seed_sticky_completed_plan(sb, conversation_id=conv2, org_id=org_id, user_id=user_id)
        t_unrelated = await chat_turn(
            ac,
            hdr,
            text="What workflows have been ran?",
            conversation_id=conv2,
            org_id=org_id,
            mode="fast",
            tools=fast_tools,
        )
        t_yes = await chat_turn(
            ac,
            hdr,
            text="yes",
            conversation_id=conv2,
            org_id=org_id,
            mode="fast",
            tools=fast_tools,
        )
        j2 = judge_stale_plan(unrelated=t_unrelated, yes_turn=t_yes)
        artifact["repros"]["stalePlanSequence"] = {
            "conversationId": conv2,
            "bootstrapHttp": bootstrap.get("http"),
            "seededStickyCompletedPlan": True,
            "turns": [
                {
                    "user": t["user"],
                    "http": t["http"],
                    "assistant": (t.get("assistant") or "")[:500],
                    "pending": (
                        (t.get("task_state") or {}).get("pending_task")
                        if isinstance(t.get("task_state"), dict)
                        else None
                    ),
                    "current_plan": (
                        (t.get("task_state") or {}).get("current_plan")
                        if isinstance(t.get("task_state"), dict)
                        else None
                    ),
                    "tools": _tool_names(t),
                    "at": t.get("at"),
                }
                for t in (t_unrelated, t_yes)
            ],
            "judgment": j2,
        }

        # Audit pointers for conv1/conv2
        try:
            rows = (
                sb.table("audit_events")
                .select("action,created_at,metadata")
                .eq("org_id", org_id)
                .order("created_at", desc=True)
                .limit(80)
                .execute()
            )
            relevant = []
            for row in rows.data or []:
                meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
                blob = json.dumps(meta) + str(row.get("action") or "")
                if conv1 in blob or conv2 in blob:
                    relevant.append(
                        {
                            "action": row.get("action"),
                            "created_at": row.get("created_at"),
                            "tool": meta.get("toolName") or meta.get("tool_name"),
                        }
                    )
            artifact["auditSample"] = relevant[:25]
        except Exception as exc:  # noqa: BLE001
            artifact["auditSampleError"] = str(exc)

    artifact["overall"] = {
        "fastRunHistory": artifact["repros"]["fastRunHistory"]["judgment"]["verdict"],
        "stalePlanSequence": artifact["repros"]["stalePlanSequence"]["judgment"]["verdict"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact["overall"], indent=2))
    print(f"wrote {OUT}")
    print(f"tip={artifact.get('tipShaObserved')} conv1={conv1} conv2={conv2}")
    if artifact["overall"]["fastRunHistory"] != "PASS":
        return 2
    if artifact["overall"]["stalePlanSequence"] != "PASS":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
