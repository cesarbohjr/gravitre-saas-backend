#!/usr/bin/env python3
"""Live typed baseline for Bug A, then spoken Bug B only if typed PASSes.

Expects production git_sha=9f3da98a. Isolated org only. Does not approve writes.
"""
from __future__ import annotations

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

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()
CLONE_ID = "d4fb0fcf-7b92-40e2-8139-75d8e24c7972"
OUT = ROOT / "docs" / "delivery" / "google-ads-bug-a-typed-baseline-live.json"
CHAT_TIMEOUT = 300.0
VOICE_TIMEOUT = 240.0

_src = (ROOT / "scripts" / "verify-hubspot-honesty-google-ads-close-live.py").read_text(
    encoding="utf-8"
)
_m = re.search(r'GOOGLE_ADS_PROMPT = """(.*?)"""', _src, re.S)
if not _m:
    raise SystemExit("FAIL: could not load GOOGLE_ADS_PROMPT")
GOOGLE_ADS_PROMPT = _m.group(1).strip()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if merged.get(k):
            os.environ[k] = merged[k]
    return merged


def parse_chat_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    connected_seen: list[list[str]] = []
    pending: dict[str, Any] | None = None
    explanations: list[str] = []
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
        if o.get("type") == "text-delta":
            texts.append(str(o.get("delta") or ""))
        data = o.get("data") if isinstance(o.get("data"), dict) else o
        if not isinstance(data, dict):
            continue
        ci = data.get("connectedIntegrations")
        if isinstance(ci, list):
            connected_seen.append([str(x) for x in ci])
        pt = data.get("pendingTask") or o.get("pendingTask")
        if isinstance(pt, dict):
            pending = pt
        if data.get("answerExplanation"):
            explanations.append(str(data["answerExplanation"])[:200])
    return {
        "assistant": "".join(texts).strip(),
        "pending_task": pending,
        "connected_seen": connected_seen,
        "explanations": explanations[:12],
    }


def ads_in_list(rows: list[list[str]] | list[str] | None) -> bool:
    if not rows:
        return False
    if rows and isinstance(rows[0], str):
        lowered = [str(x).lower() for x in rows]
        return "google_ads" in lowered or "googleads" in lowered
    for row in rows:
        lowered = [str(x).lower() for x in row]
        if "google_ads" in lowered or "googleads" in lowered:
            return True
    return False


def extract_structure_create(pending: dict[str, Any] | None, task_state: dict[str, Any] | None) -> dict[str, Any]:
    sources = []
    if isinstance(pending, dict):
        sources.append(pending)
        params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
        sources.append(params)
    if isinstance(task_state, dict):
        sources.append(task_state.get("pending_task") or {})
        sources.append(task_state.get("clarified_params") or {})
    actions: list[str] = []
    labels: list[str] = []
    step_count = None
    pending_type = None
    pending_status = None
    for src in sources:
        if not isinstance(src, dict):
            continue
        pending_type = pending_type or src.get("type")
        pending_status = pending_status or src.get("status")
        steps = src.get("steps") or []
        if isinstance(steps, list) and steps and step_count is None:
            step_count = len(steps)
        for step in steps if isinstance(steps, list) else []:
            if not isinstance(step, dict):
                continue
            labels.append(str(step.get("label") or step.get("description") or ""))
            plan = step.get("plan") if isinstance(step.get("plan"), dict) else {}
            action = str(
                plan.get("invoke_action")
                or plan.get("invokeAction")
                or step.get("invoke_action")
                or ""
            )
            if action:
                actions.append(action)
    joined = " ".join(actions + labels).lower()
    return {
        "pending_type": pending_type,
        "pending_status": pending_status,
        "step_count": step_count,
        "invoke_actions": actions,
        "has_structure_create": any("structure.create" in a.lower() for a in actions)
        or "structure.create" in joined,
        "labels": labels[:8],
    }


def classify_text(text: str) -> dict[str, Any]:
    lowered = (text or "").lower().replace("\u2019", "'")
    return {
        "workflow_steal": "draft workflow" in lowered or "create_workflow" in lowered,
        "problem_aware_steal": "problem aware" in lowered and "draft workflow" in lowered,
        "not_connected": "not connected" in lowered and "google ads" in lowered,
        "orch_plan": "step orchestration" in lowered,
        "approval": "reply **yes**" in lowered or "reply yes" in lowered,
        "mentions_campaigns": "campaign" in lowered,
    }


def slim_audits(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for a in rows:
        p = a.get("metadata") or {}
        if isinstance(p, str):
            try:
                p = json.loads(p)
            except json.JSONDecodeError:
                p = {}
        out.append(
            {
                "action": a.get("action"),
                "created_at": a.get("created_at"),
                "model": (p or {}).get("model"),
                "outcome_kind": (p or {}).get("outcome_kind"),
                "connected_integrations": (p or {}).get("connected_integrations"),
                "tool_invoke_action": (p or {}).get("tool_invoke_action"),
                "tool_name": (p or {}).get("tool_name"),
            }
        )
    return out


def main() -> int:
    env = load_env()
    from supabase import create_client

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
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "x-org-id": org_id,
    }
    out: dict[str, Any] = {
        "probe": "google_ads_bug_a_typed_baseline_then_spoken",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "org_id": org_id,
        "expect_sha": EXPECT_SHA,
        "clone_id": CLONE_ID,
    }
    with httpx.Client(timeout=CHAT_TIMEOUT) as client:
        health = client.get(f"{BASE}/health", timeout=30).json()
        sha = str(health.get("git_sha") or "")
        out["git_sha"] = sha
        out["health_timestamp"] = health.get("timestamp")
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            out["verdict"] = f"NOT RUN — tip mismatch got={sha} expect={EXPECT_SHA}"
            OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
            print(json.dumps({"verdict": out["verdict"], "git_sha": sha}, indent=2))
            return 1
        clone = (
            sb.table("connectors")
            .select("id,type,vendor,status,environment,org_id")
            .eq("id", CLONE_ID)
            .limit(1)
            .execute()
            .data
            or []
        )
        out["clone"] = clone[0] if clone else None
        if not clone or str(clone[0].get("org_id")) != org_id:
            out["verdict"] = "FAIL — clone d4fb0fcf not in isolated org"
            OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
            print(json.dumps(out, indent=2, default=str)[:2000])
            return 1

        typed_conv = str(uuid.uuid4())
        create = client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"ads-bug-a-typed-{datetime.now(timezone.utc).strftime('%H%M%S')}", "id": typed_conv},
            timeout=60,
        )
        if create.status_code < 400:
            typed_conv = str((create.json() or {}).get("id") or typed_conv)
        out["typed_conversation_id"] = typed_conv
        r = client.post(
            f"{BASE}/api/assistant/chat",
            headers=headers,
            json={
                "messages": [{"role": "user", "parts": [{"type": "text", "text": GOOGLE_ADS_PROMPT}]}],
                "org_id": org_id,
                "mode": "agent",
                "conversationId": typed_conv,
                "conversation_id": typed_conv,
                "spoken_mode": False,
            },
            timeout=CHAT_TIMEOUT,
        )
        parsed = parse_chat_sse(r.text)
        conv_row = (
            sb.table("conversations")
            .select("id,task_state")
            .eq("id", typed_conv)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        task_state = (conv_row[0].get("task_state") if conv_row else {}) or {}
        audits = (
            sb.table("audit_events")
            .select("action,created_at,metadata,resource_id")
            .eq("org_id", org_id)
            .eq("resource_id", typed_conv)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data
            or []
        )
        audit_slim = slim_audits(audits)
        audit_connected: list[str] = []
        for a in audit_slim:
            if a.get("connected_integrations"):
                audit_connected = list(a["connected_integrations"])
                break
        structure = extract_structure_create(parsed.get("pending_task"), task_state)
        text_class = classify_text(str(parsed.get("assistant") or ""))
        google_ads_listed = ads_in_list(parsed.get("connected_seen")) or ads_in_list(audit_connected)
        typed_pass = bool(
            google_ads_listed
            and structure.get("has_structure_create")
            and str(structure.get("pending_type") or "") == "connector_orchestration"
            and not text_class.get("workflow_steal")
            and not text_class.get("not_connected")
        )
        typed = {
            "http_status": r.status_code,
            "assistant_head": (parsed.get("assistant") or "")[:1200],
            "connected_seen": parsed.get("connected_seen"),
            "google_ads_in_sse": ads_in_list(parsed.get("connected_seen")),
            "audit_connected_integrations": audit_connected,
            "google_ads_in_audit": ads_in_list(audit_connected),
            "structure": structure,
            "class": text_class,
            "explanations": parsed.get("explanations"),
            "pending_task": parsed.get("pending_task"),
            "task_state_pending": (task_state or {}).get("pending_task"),
            "audits": audit_slim[:8],
            "pass": typed_pass,
        }
        out["typed"] = typed
        out["typed_verdict"] = (
            "PASS — google_ads listed and structure.create staged"
            if typed_pass
            else "FAIL — typed did not stage google_ads.structure.create with Ads in connected_integrations"
        )

        spoken = None
        if typed_pass:
            spoken_conv = str(uuid.uuid4())
            create_s = client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"ads-bug-b-spoken-{datetime.now(timezone.utc).strftime('%H%M%S')}"},
                timeout=60,
            )
            if create_s.status_code < 400:
                spoken_conv = str((create_s.json() or {}).get("id") or spoken_conv)
            voice_headers = {
                **{k: v for k, v in headers.items() if k != "Accept"},
                "Accept": "application/x-ndjson",
            }
            complete_text = ""
            deltas: list[str] = []
            event_types: list[str] = []
            with client.stream(
                "POST",
                f"{BASE}/api/voice/session/turn",
                headers=voice_headers,
                json={
                    "text": GOOGLE_ADS_PROMPT,
                    "conversation_id": spoken_conv,
                    "turn_id": str(uuid.uuid4()),
                    "history": [],
                },
                timeout=VOICE_TIMEOUT,
            ) as vr:
                spoken_http = vr.status_code
                if spoken_http >= 400:
                    spoken_raw = vr.read().decode("utf-8", errors="replace")
                    spoken = {
                        "http_status": spoken_http,
                        "error": spoken_raw[:800],
                        "conversation_id": spoken_conv,
                    }
                else:
                    for line in vr.iter_lines():
                        if not line:
                            continue
                        try:
                            ev = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(ev, dict):
                            continue
                        et = str(ev.get("type") or "")
                        event_types.append(et)
                        if et == "voice.text.delta":
                            deltas.append(str(ev.get("delta") or ""))
                        if et == "voice.turn.complete":
                            complete_text = str(ev.get("text") or "")
                    assistant = (complete_text or "".join(deltas)).strip()
                    spoken_row = (
                        sb.table("conversations")
                        .select("id,task_state")
                        .eq("id", spoken_conv)
                        .eq("org_id", org_id)
                        .limit(1)
                        .execute()
                        .data
                        or []
                    )
                    spoken_state = (spoken_row[0].get("task_state") if spoken_row else {}) or {}
                    spoken_audits = slim_audits(
                        (
                            sb.table("audit_events")
                            .select("action,created_at,metadata,resource_id")
                            .eq("org_id", org_id)
                            .eq("resource_id", spoken_conv)
                            .order("created_at", desc=True)
                            .limit(20)
                            .execute()
                            .data
                            or []
                        )
                    )
                    spoken_connected: list[str] = []
                    for a in spoken_audits:
                        if a.get("connected_integrations"):
                            spoken_connected = list(a["connected_integrations"])
                            break
                    spoken_structure = extract_structure_create(None, spoken_state)
                    spoken_class = classify_text(assistant)
                    spoken = {
                        "http_status": spoken_http,
                        "conversation_id": spoken_conv,
                        "assistant_head": assistant[:1200],
                        "event_types": event_types[:40],
                        "used_complete_text": bool(complete_text.strip()),
                        "class": spoken_class,
                        "audit_connected_integrations": spoken_connected,
                        "google_ads_in_audit": ads_in_list(spoken_connected),
                        "structure": spoken_structure,
                        "task_state_pending": (spoken_state or {}).get("pending_task"),
                        "audits": spoken_audits[:8],
                    }
            out["spoken"] = spoken
            if spoken and spoken.get("class", {}).get("workflow_steal"):
                out["bug_b_verdict"] = (
                    "FAIL — isolated Bug B: spoken still stole quoted content into create_workflow "
                    "after typed staged a real Ads plan"
                )
            elif spoken and spoken.get("structure", {}).get("has_structure_create"):
                out["bug_b_verdict"] = "PASS — spoken staged google_ads.structure.create like typed"
            else:
                out["bug_b_verdict"] = "INCONCLUSIVE — spoken did not match typed Ads plan or workflow steal"
        else:
            out["spoken"] = None
            out["bug_b_verdict"] = "NOT RUN — typed baseline did not PASS"

    out["finished_at"] = datetime.now(timezone.utc).isoformat()
    out["verdict"] = out["typed_verdict"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "git_sha": out.get("git_sha"),
                "typed_verdict": out.get("typed_verdict"),
                "typed_pass": (out.get("typed") or {}).get("pass"),
                "google_ads_in_sse": (out.get("typed") or {}).get("google_ads_in_sse"),
                "google_ads_in_audit": (out.get("typed") or {}).get("google_ads_in_audit"),
                "structure": (out.get("typed") or {}).get("structure"),
                "typed_class": (out.get("typed") or {}).get("class"),
                "typed_head": (out.get("typed") or {}).get("assistant_head", "")[:500],
                "typed_conversation_id": out.get("typed_conversation_id"),
                "bug_b_verdict": out.get("bug_b_verdict"),
                "spoken_head": ((out.get("spoken") or {}) or {}).get("assistant_head", "")[:400]
                if out.get("spoken")
                else None,
                "spoken_conversation_id": ((out.get("spoken") or {}) or {}).get("conversation_id"),
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if typed_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
