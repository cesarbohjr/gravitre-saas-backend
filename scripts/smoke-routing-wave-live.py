#!/usr/bin/env python3
"""Routing-wave prod live traces (PR #97 / sha 65998eb7).

Trace A: fast honesty — effectiveMode=fast AND routingTier=simple (no agent upgrade)
Trace B: write intent — routingTier multi_step|research (stop at pending approval)
Trace C: deepen/research — routingTier=research or escalation thereto
Trace D: informational — audit_events assistant.routing.escalated count since start

Verdict PASS only if A+B+C pass.
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

import jwt
from dotenv import dotenv_values
from httpx import AsyncClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT))
OUT = Path(
    os.environ.get(
        "ROUTING_WAVE_JSON_OUT",
        str(ROOT / "docs" / "delivery" / "routing-wave-prod-live.json"),
    )
)
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
BASE = os.environ.get("ROUTING_WAVE_BASE_URL", "https://api.gravitre.app").rstrip("/")
EXPECTED_SHA_PREFIX = "65998eb7"
# Prod may roll forward; accept known descendants that contain PR #97 merge.
# Update when follow-up routing fixes land (clarify SSE / dynamic iterations).
ACCEPT_SHA_PREFIXES = ("65998eb7", "3aff41ad", "b8c13fa0", "9c5368e3", "91f785db")
CHAT_TIMEOUT = 600.0
# When set, allow any prod SHA (use after merge while waiting to pin the new prefix).
ALLOW_ANY_PROD_SHA = os.environ.get("ROUTING_WAVE_ALLOW_ANY_SHA", "").strip() in {
    "1",
    "true",
    "yes",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> None:
    for p in (
        BACKEND / ".env",
        BACKEND / ".env.operator.local",
        ROOT / ".env",
        ROOT / ".env.operator.local",
    ):
        if not p.is_file():
            continue
        try:
            for k, v in dotenv_values(p).items():
                if v:
                    os.environ.setdefault(k, v)
        except Exception:
            pass


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    tools: list[dict] = []
    intel: list[dict] = []
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
            texts.append(o.get("delta") or "")
        if t in ("tool-input-available", "tool-output-available") or (
            isinstance(t, str) and "tool" in t
        ):
            tools.append({k: o.get(k) for k in ("type", "toolName", "toolCallId") if k in o})
        if t == "data-intelligence":
            d = o.get("data") or {}
            routing = d.get("routing") if isinstance(d.get("routing"), dict) else {}
            pend = d.get("pendingTask") or d.get("pending_task")
            intel.append(
                {
                    "effectiveMode": d.get("effectiveMode"),
                    "pipelineTier": d.get("pipelineTier"),
                    "routingTier": d.get("routingTier") or routing.get("routingTier"),
                    "routing": routing or None,
                    "dialogueMode": d.get("dialogueMode"),
                    "expl": (d.get("answerExplanation") or "")[:160],
                    "pending": pend,
                    "executionGate": d.get("executionGate") or d.get("execution_gate"),
                }
            )
    return {"text": "".join(texts), "tools": tools, "intel": intel}


def extract_routing(intel: list[dict]) -> dict[str, Any]:
    """Best-effort final + all tiers seen from data-intelligence events."""
    tiers: list[str] = []
    modes: list[str] = []
    pipelines: list[str] = []
    last: dict[str, Any] = {}
    for item in intel:
        rt = item.get("routingTier")
        if not rt and isinstance(item.get("routing"), dict):
            rt = item["routing"].get("routingTier")
        if isinstance(rt, str) and rt:
            tiers.append(rt)
        em = item.get("effectiveMode")
        if isinstance(em, str) and em:
            modes.append(em)
        pt = item.get("pipelineTier")
        if isinstance(pt, str) and pt:
            pipelines.append(pt)
        last = item
    final_tier = tiers[-1] if tiers else None
    final_mode = modes[-1] if modes else None
    return {
        "routing_tiers_seen": tiers,
        "effective_modes_seen": modes,
        "pipeline_tiers_seen": pipelines,
        "final_routingTier": final_tier,
        "final_effectiveMode": final_mode,
        "final_pipelineTier": pipelines[-1] if pipelines else None,
        "last_intel": {
            "effectiveMode": last.get("effectiveMode"),
            "pipelineTier": last.get("pipelineTier"),
            "routingTier": last.get("routingTier"),
            "routing": last.get("routing"),
            "expl": last.get("expl"),
            "pending": last.get("pending"),
        }
        if last
        else {},
    }


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
    mode: str,
) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
        "org_id": ORG,
        "tools": tools,
        "mode": mode,
        "conversation_id": conversation_id,
    }
    # Stream-accumulate — prod sometimes closes chunked SSE early.
    chunks: list[bytes] = []
    status = 0
    try:
        async with ac.stream(
            "POST", "/api/assistant/chat", json=body, headers=hdr, timeout=CHAT_TIMEOUT
        ) as r:
            status = r.status_code
            async for part in r.aiter_bytes():
                chunks.append(part)
    except Exception as exc:  # noqa: BLE001
        if not chunks:
            raise
        print(f"WARN chat stream truncated ({exc}); using {sum(len(c) for c in chunks)} bytes")
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    parsed = parse_sse(raw)
    routing = extract_routing(parsed["intel"])
    state_hdr = {k: v for k, v in hdr.items() if k != "Accept"}
    pending = None
    task_state = None
    try:
        st = await ac.get(
            f"/api/assistant/conversation/{conversation_id}/state",
            headers=state_hdr,
            timeout=60.0,
        )
        if st.status_code == 200:
            task_state = st.json().get("task_state") or {}
            pending = task_state.get("pending_task")
    except Exception as e:
        task_state = {"state_error": str(e)}
    return {
        "http": status,
        "conversation_id": conversation_id,
        "mode_requested": mode,
        "message": text,
        "text": (parsed["text"] or "")[:600],
        "tools_seen": parsed["tools"][:20],
        "intel_count": len(parsed["intel"]),
        "sse_pending": last_pending(parsed["intel"]),
        "db_pending": pending,
        "task_state_keys": list(task_state.keys()) if isinstance(task_state, dict) else None,
        **routing,
    }


def audit_escalations(client, *, since_iso: str, limit: int = 80) -> list[dict]:
    rows = (
        client.table("audit_events")
        .select("id,action,resource_type,resource_id,metadata,created_at")
        .eq("org_id", ORG)
        .eq("action", "assistant.routing.escalated")
        .gte("created_at", since_iso)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    slim = []
    for row in rows:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        slim.append(
            {
                "id": row.get("id"),
                "created_at": row.get("created_at"),
                "resource_id": row.get("resource_id"),
                "from": meta.get("from") or meta.get("from_tier") or meta.get("previous"),
                "to": meta.get("to") or meta.get("to_tier") or meta.get("tier"),
                "reason": meta.get("reason"),
                "metadata_keys": sorted(meta.keys())[:20],
            }
        )
    return slim


async def main() -> int:
    load_env()
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(BACKEND))
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    import importlib.util

    auth_path = ROOT / "scripts" / "smoke_auth.py"
    spec = importlib.util.spec_from_file_location("smoke_auth", auth_path)
    smoke_auth = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(smoke_auth)
    actor, email = smoke_auth.resolve_smoke_actor_and_email(client, org_id=ORG, env=dict(os.environ))
    url = os.environ["SUPABASE_URL"].rstrip("/")
    now = int(time.time())
    tok = jwt.encode(
        {
            "sub": actor,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
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

    started = utcnow()
    report: dict[str, Any] = {
        "probe": "routing_wave_prod_live",
        "pr": 97,
        "expected_sha_prefix": EXPECTED_SHA_PREFIX,
        "started_at": started,
        "base_url": BASE,
        "org_id": ORG,
        "actor_id": actor,
        "traces": {},
        "trace_d": {},
    }

    async with AsyncClient(base_url=BASE, timeout=CHAT_TIMEOUT, verify=False) as ac:
        health = (await ac.get("/health")).json()
        report["prod_health"] = health
        sha = str(health.get("git_sha") or "")
        report["prod_sha"] = sha
        report["prod_sha_ok"] = ALLOW_ANY_PROD_SHA or any(
            sha.startswith(p) for p in ACCEPT_SHA_PREFIXES
        )
        report["accept_sha_prefixes"] = list(ACCEPT_SHA_PREFIXES)
        report["allow_any_prod_sha"] = ALLOW_ANY_PROD_SHA
        report["contains_pr97_note"] = (
            "3aff41ad merges main after 65998eb7 (#97); follow-up clarify-SSE fix may supersede"
        )
        if not report["prod_sha_ok"]:
            report["verdict"] = "BLOCKED_WRONG_SHA"
            report["finished_at"] = utcnow()
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            print("WROTE", OUT)
            return 1

        # ---- Trace A: Fast honesty ----
        # Unique nonce avoids Tier-0 answer cache, which emits data-intelligence
        # without effectiveMode/routingTier (early return path).
        turn_a = None
        cid_a = ""
        for attempt in range(1, 4):
            cid_a = str(uuid.uuid4())
            nonce = uuid.uuid4().hex[:8]
            turn_a = await chat(
                ac,
                hdr,
                text=f"What connectors are connected? (routing-wave A {nonce})",
                tools=["knowledge_base", "agent_status", "connector_status", "apollo_lists_search"],
                conversation_id=cid_a,
                mode="fast",
            )
            turn_a["attempt"] = attempt
            if turn_a.get("final_effectiveMode") and turn_a.get("final_routingTier"):
                break
        assert turn_a is not None
        em = turn_a.get("final_effectiveMode")
        rt = turn_a.get("final_routingTier")
        modes = turn_a.get("effective_modes_seen") or []
        upgraded = any(m in {"agent", "reasoning", "standard"} for m in modes if m != "fast")
        # Must stay fast; routingTier simple
        pass_a = (
            em == "fast"
            and rt == "simple"
            and "agent" not in modes
            and turn_a.get("http") == 200
        )
        report["traces"]["A_fast_honesty"] = {
            "pass": pass_a,
            "criteria": "effectiveMode=fast AND routingTier=simple; must NOT upgrade to agent",
            "conversation_id": cid_a,
            "result": turn_a,
            "upgraded_away_from_fast": upgraded or ("agent" in modes),
        }

        # ---- Trace B: Write intent → multi_step ----
        cid_b = str(uuid.uuid4())
        turn_b = await chat(
            ac,
            hdr,
            text="In Apollo, create a contact list named Routing Wave Live.",
            tools=["apollo_lists_create", "connector_status", "knowledge_base"],
            conversation_id=cid_b,
            mode="standard",
        )
        rt_b = turn_b.get("final_routingTier")
        tiers_b = turn_b.get("routing_tiers_seen") or []
        pass_b = (
            turn_b.get("http") == 200
            and (
                rt_b in {"multi_step", "research"}
                or any(t in {"multi_step", "research"} for t in tiers_b)
            )
        )
        pending_b = turn_b.get("db_pending") or turn_b.get("sse_pending")
        report["traces"]["B_write_intent"] = {
            "pass": pass_b,
            "criteria": "routingTier multi_step OR research (not simple); pending approval OK (not confirmed)",
            "conversation_id": cid_b,
            "result": turn_b,
            "pending_gate": pending_b,
            "stopped_at_pending": bool(isinstance(pending_b, dict) and pending_b.get("type")),
            "note": "Did not confirm write — prefer stop at pending approval",
        }

        # ---- Trace C: Deepen / research ----
        # Prefer connected connectors (Apollo/Pipedrive) so deepen can run ReAct;
        # clarification early-returns must still emit routingTier=research.
        turn_c = None
        cid_c = ""
        c_attempts: list[dict] = []
        c_modes = ["standard", "fast", "standard", "fast", "reasoning"]
        c_msg = (
            "go deeper with a full analysis comparing our Apollo and Pipedrive pipeline health"
        )
        for attempt, mode_c in enumerate(c_modes, start=1):
            cid_c = str(uuid.uuid4())
            nonce = uuid.uuid4().hex[:8]
            turn_c = await chat(
                ac,
                hdr,
                text=f"{c_msg} [routing-wave C {nonce}]",
                tools=["knowledge_base", "connector_status", "agent_status"],
                conversation_id=cid_c,
                mode=mode_c,
            )
            turn_c["attempt"] = attempt
            c_attempts.append(
                {
                    "attempt": attempt,
                    "mode": mode_c,
                    "conversation_id": cid_c,
                    "final_routingTier": turn_c.get("final_routingTier"),
                    "tiers_seen": turn_c.get("routing_tiers_seen"),
                    "effectiveMode": turn_c.get("final_effectiveMode"),
                    "http": turn_c.get("http"),
                    "text_head": (turn_c.get("text") or "")[:200],
                    "expl": ((turn_c.get("last_intel") or {}).get("expl") or "")[:160],
                }
            )
            if turn_c.get("final_routingTier") == "research" or (
                "research" in (turn_c.get("routing_tiers_seen") or [])
            ):
                break
        assert turn_c is not None
        rt_c = turn_c.get("final_routingTier")
        tiers_c = turn_c.get("routing_tiers_seen") or []
        pass_c = turn_c.get("http") == 200 and (
            rt_c == "research" or any(t == "research" for t in tiers_c)
        )
        report["traces"]["C_deepen_research"] = {
            "pass": pass_c,
            "criteria": "routingTier=research OR escalation to research",
            "conversation_id": cid_c,
            "attempts": c_attempts,
            "result": turn_c,
        }

        # ---- Trace D: escalation audit (informational) ----
        esc = audit_escalations(client, since_iso=started)
        report["trace_d"] = {
            "informational": True,
            "pass": True,
            "criteria": "count assistant.routing.escalated since script start (>=0 always; ideal >=1 if B/C escalated)",
            "count": len(esc),
            "events": esc[:20],
            "note": (
                f"{len(esc)} escalation audit row(s) since {started}"
                if esc
                else "zero assistant.routing.escalated rows since script start (may classify at research/multi_step without mid-turn escalate)"
            ),
        }

    a_ok = report["traces"]["A_fast_honesty"]["pass"]
    b_ok = report["traces"]["B_write_intent"]["pass"]
    c_ok = report["traces"]["C_deepen_research"]["pass"]
    report["finished_at"] = utcnow()
    report["verdict"] = "PASS" if (a_ok and b_ok and c_ok) else "FAIL"
    report["summary"] = {
        "A": a_ok,
        "B": b_ok,
        "C": c_ok,
        "D_escalation_count": report["trace_d"]["count"],
        "prod_sha": sha,
        "verdict": report["verdict"],
        "evidence": {
            "A_effectiveMode": report["traces"]["A_fast_honesty"]["result"].get("final_effectiveMode"),
            "A_routingTier": report["traces"]["A_fast_honesty"]["result"].get("final_routingTier"),
            "A_conversation_id": cid_a,
            "B_routingTier": report["traces"]["B_write_intent"]["result"].get("final_routingTier"),
            "B_tiers_seen": report["traces"]["B_write_intent"]["result"].get("routing_tiers_seen"),
            "B_pending": bool(report["traces"]["B_write_intent"].get("stopped_at_pending")),
            "B_conversation_id": cid_b,
            "C_routingTier": report["traces"]["C_deepen_research"]["result"].get("final_routingTier"),
            "C_tiers_seen": report["traces"]["C_deepen_research"]["result"].get("routing_tiers_seen"),
            "C_conversation_id": cid_c,
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(json.dumps({"verdict": report["verdict"], "prod_sha": sha, "wrote": str(OUT)}, indent=2))
    print("WROTE", OUT)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
