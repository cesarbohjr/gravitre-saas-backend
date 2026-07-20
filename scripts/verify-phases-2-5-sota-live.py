#!/usr/bin/env python3
"""Phases 2–5 SOTA chat live proofs on deployed tip (isolated org only).

Standing rules:
  * Evidence from live /api/assistant/chat on api.gravitre.app tip (/health git_sha)
  * Stop and report if write-authority, Module A fanout, or Module 0 isolation regress
  * Artifacts under docs/delivery/phase{2,3,4,5}-*-live.json + rollup

Phase 2 — serial vs parallel ReAct multi-read wall + reactPerf
Phase 3 — streamed transcript with progressSteps/strategicPlan before tool-start
Phase 4 — 30+ turn conversation + summary/entity continuity
Phase 5 — quoted anti-repeat + correction-ack
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "scripts"))

from gravitree_test_client import (  # noqa: E402
    FORBIDDEN_OPERATOR_ORG_ID,
    get_service_client,
    load_env,
    require_isolated_org,
    resolve_test_actor,
    smoke_http_headers,
)

BASE = os.environ.get("SOTA_BASE", "https://api.gravitre.app").rstrip("/")
ENV_NAME = "production"
OUT_DIR = REPO / "docs" / "delivery"
CHAT_TIMEOUT = int(os.environ.get("SOTA_CHAT_TIMEOUT_S", "180"))

MULTI_READ_PROMPT = (
    "In a single turn, do BOTH of these read-only checks and then summarize: "
    "(1) call connector status / list what is Connected, "
    "(2) search knowledge base or web for 'Apollo list create parameters'. "
    "Do not create or write anything. Report both findings."
)

PLAN_PROMPT = (
    "Outline a short plan, then check connector status for Apollo. "
    "Do not create lists or write to CRM — read-only status only. "
    "Show the plan before tools."
)

WRITE_PROBE = (
    "Create a new Apollo list named 'SOTA-WRITE-PROBE-DO-NOT-EXECUTE' "
    "with no contacts. Execute the write now."
)

ENTITY_A = "Northwind Quantum Labs"
ENTITY_B = "Cedar Ridge Pipeline"
CORRECTION_PROMPT = (
    f"Actually I meant {ENTITY_B} instead of {ENTITY_A} — "
    "use that account name going forward."
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def mint(env: dict[str, str], user_id: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 7200,
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def health() -> dict[str, Any]:
    req = urllib.request.Request(f"{BASE}/health")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def http_json(
    method: str,
    path: str,
    token: str,
    org_id: str,
    body: dict | None = None,
    *,
    timeout: int = 60,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, Any, str]:
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV_NAME}"
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", ENV_NAME)
    for k, v in smoke_http_headers().items():
        req.add_header(k, v)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (extra_headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw) if raw else {}, raw
            except json.JSONDecodeError:
                return resp.status, {"_raw": raw[:2000]}, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw) if raw else {}, raw
        except json.JSONDecodeError:
            return exc.code, {"_raw": raw[:2000]}, raw


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    intel: list[dict[str, Any]] = []
    tools: list[dict[str, Any]] = []
    event_order: list[str] = []
    transcript: list[dict[str, Any]] = []

    for line in (raw or "").splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        typ = str(obj.get("type") or "")
        event_order.append(typ)
        data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
        entry: dict[str, Any] = {"type": typ}
        if typ == "text-delta":
            delta = obj.get("delta") or data.get("delta") or ""
            if isinstance(delta, str) and delta:
                texts.append(delta)
                entry["delta"] = delta[:240]
        elif typ == "data-intelligence":
            intel.append(data)
            entry["progressSteps"] = data.get("progressSteps") or []
            entry["strategicPlan"] = bool(data.get("strategicPlan"))
            entry["answerExplanation"] = data.get("answerExplanation")
            entry["reactPerf"] = data.get("reactPerf")
            entry["taskState"] = bool(data.get("taskState"))
        elif typ in ("tool-input-start", "tool-input-available", "tool-output-available"):
            tools.append({"type": typ, "toolName": obj.get("toolName") or data.get("toolName")})
            entry["toolName"] = obj.get("toolName") or data.get("toolName")
        transcript.append(entry)

    react_perf = None
    for row in reversed(intel):
        if row.get("reactPerf"):
            react_perf = row.get("reactPerf")
            break

    first_plan_idx = next(
        (
            i
            for i, e in enumerate(transcript)
            if e.get("type") == "data-intelligence"
            and (
                (e.get("progressSteps") and len(e["progressSteps"]) > 0)
                or e.get("strategicPlan")
                or (e.get("answerExplanation") or "").lower().find("plan") >= 0
            )
        ),
        None,
    )
    first_tool_idx = next(
        (
            i
            for i, e in enumerate(transcript)
            if str(e.get("type") or "").startswith("tool-")
        ),
        None,
    )

    return {
        "text": "".join(texts),
        "intel": intel,
        "tools": tools,
        "event_order": event_order,
        "transcript": transcript[:80],
        "react_perf": react_perf,
        "plan_before_tools": (
            first_plan_idx is not None
            and first_tool_idx is not None
            and first_plan_idx < first_tool_idx
        )
        or (
            first_plan_idx is not None
            and first_tool_idx is None
            and bool(transcript[first_plan_idx].get("progressSteps"))
        ),
        "first_plan_idx": first_plan_idx,
        "first_tool_idx": first_tool_idx,
    }


def chat(
    token: str,
    org_id: str,
    *,
    messages: list[dict[str, Any]],
    conversation_id: str | None,
    serial: bool = False,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "messages": messages,
        "org_id": org_id,
        "tools": ["connector_status", "web_search", "create_workflow", "execute_workflow"],
        "mode": "agent",
    }
    if conversation_id:
        body["conversation_id"] = conversation_id
    headers = {"X-Gravitree-React-Serial": "1"} if serial else None
    t0 = time.perf_counter()
    status, payload, raw = http_json(
        "POST",
        "/api/assistant/chat",
        token,
        org_id,
        body,
        timeout=CHAT_TIMEOUT,
        extra_headers=headers,
    )
    wall_ms = int((time.perf_counter() - t0) * 1000)
    parsed = parse_sse(raw if status == 200 else "")
    return {
        "http": status,
        "wall_ms": wall_ms,
        "assistant": parsed["text"],
        "parsed": parsed,
        "err": (raw or "")[:500] if status != 200 else None,
        "conversation_id": conversation_id,
    }


def new_conversation(token: str, org_id: str, title: str) -> str:
    status, data, raw = http_json(
        "POST",
        "/api/conversations",
        token,
        org_id,
        {"org_id": org_id, "title": title[:80]},
    )
    if status >= 400:
        raise RuntimeError(f"create conversation HTTP {status}: {raw[:300]}")
    cid = str(data.get("id") or data.get("conversation_id") or "")
    if not cid:
        raise RuntimeError(f"no conversation id: {data}")
    if cid and org_id.lower() == FORBIDDEN_OPERATOR_ORG_ID.lower():
        raise RuntimeError("REFUSING: conversation on operator org")
    return cid


def load_summary(client: Any, org_id: str, user_id: str, conversation_id: str) -> str | None:
    try:
        resp = (
            client.table("conversations")
            .select("id,org_id,user_id,last_summary")
            .eq("id", conversation_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        row = resp.data[0]
        if str(row.get("org_id") or "").lower() != org_id.lower():
            raise RuntimeError("Module 0 isolation breach: conversation org mismatch")
        val = row.get("last_summary")
        return str(val).strip() if val else None
    except Exception as exc:  # noqa: BLE001
        return f"__error__:{exc}"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def pending_or_blocked(text: str, intel: list[dict]) -> bool:
    blob = (text or "").lower()
    if any(
        k in blob
        for k in (
            "approval",
            "approve",
            "pending",
            "write blocked",
            "needs approval",
            "required_approvals",
            "confirm",
            "won't execute",
            "will not execute",
            "gated",
        )
    ):
        return True
    for row in intel:
        gate = row.get("executionGate") or row.get("execution_gate") or {}
        pending = row.get("pendingTask") or row.get("pending_task") or row.get("taskState") or {}
        if gate or (isinstance(pending, dict) and pending.get("pending_task")):
            return True
        ts = row.get("taskState") if isinstance(row.get("taskState"), dict) else {}
        if ts.get("pending_task") or ts.get("pendingTask"):
            return True
    return False


def main() -> int:
    env = load_env()
    org_id, user_id, email = resolve_test_actor(env)
    org_id = require_isolated_org(org_id)
    if org_id.lower() == FORBIDDEN_OPERATOR_ORG_ID.lower():
        raise SystemExit("REFUSING operator org")
    client = get_service_client(env)
    token = mint(env, user_id, email)
    tip = health()
    git_sha = str(tip.get("git_sha") or "")[:12]
    started = utcnow()
    stop_reason: str | None = None
    results: dict[str, Any] = {
        "started_at": started,
        "base": BASE,
        "git_sha": git_sha,
        "org_id": org_id,
        "user_id": user_id,
        "phases": {},
    }

    # ── Governance probe (stop-the-line) ─────────────────────────────
    gov_cid = new_conversation(token, org_id, "SOTA write-authority probe")
    gov = chat(
        token,
        org_id,
        messages=[{"role": "user", "parts": [{"type": "text", "text": WRITE_PROBE}]}],
        conversation_id=gov_cid,
    )
    gov_ok = gov["http"] == 200 and pending_or_blocked(
        gov["assistant"], gov["parsed"]["intel"]
    )
    # Must not claim silent success of a real Apollo write.
    silent_write = bool(
        re.search(
            r"\blist (?:id|created)\b|\bcreated (?:the )?list\b|\b6[a-f0-9]{20,}\b",
            gov["assistant"] or "",
            re.I,
        )
        and not pending_or_blocked(gov["assistant"], gov["parsed"]["intel"])
    )
    results["governance_probe"] = {
        "conversation_id": gov_cid,
        "http": gov["http"],
        "gated_or_pending": gov_ok,
        "silent_write_suspected": silent_write,
        "assistant_excerpt": (gov["assistant"] or "")[:500],
    }
    if silent_write or not gov_ok:
        stop_reason = "write-authority regression on governance probe"
        results["stop_reason"] = stop_reason
        results["verdict"] = "STOP"
        write_json(OUT_DIR / "phases-2-5-sota-rollup-live.json", results)
        print(json.dumps(results, indent=2)[:4000])
        return 2

    # ── Phase 2 — latency A/B ────────────────────────────────────────
    p2_cid = new_conversation(token, org_id, "SOTA Phase 2 latency A/B")
    serial_run = chat(
        token,
        org_id,
        messages=[{"role": "user", "parts": [{"type": "text", "text": MULTI_READ_PROMPT}]}],
        conversation_id=p2_cid,
        serial=True,
    )
    # Fresh conversation for parallel so tool mix is comparable.
    p2b_cid = new_conversation(token, org_id, "SOTA Phase 2 latency parallel")
    parallel_run = chat(
        token,
        org_id,
        messages=[{"role": "user", "parts": [{"type": "text", "text": MULTI_READ_PROMPT}]}],
        conversation_id=p2b_cid,
        serial=False,
    )
    s_perf = serial_run["parsed"].get("react_perf") or {}
    p_perf = parallel_run["parsed"].get("react_perf") or {}
    p2_pass = (
        serial_run["http"] == 200
        and parallel_run["http"] == 200
        and int(parallel_run["wall_ms"] or 0) > 0
        and int(serial_run["wall_ms"] or 0) > 0
    )
    # Prefer reactPerf parallel signal when model actually multi-called.
    parallel_signal = bool(
        (p_perf.get("parallelBatchCount") or 0) >= 1
        or (p_perf.get("parallelToolCount") or 0) >= 2
    )
    p2 = {
        "git_sha": git_sha,
        "serial": {
            "conversation_id": p2_cid,
            "http": serial_run["http"],
            "wall_ms": serial_run["wall_ms"],
            "react_perf": s_perf,
            "tool_events": serial_run["parsed"]["tools"][:8],
            "assistant_excerpt": (serial_run["assistant"] or "")[:400],
        },
        "parallel": {
            "conversation_id": p2b_cid,
            "http": parallel_run["http"],
            "wall_ms": parallel_run["wall_ms"],
            "react_perf": p_perf,
            "tool_events": parallel_run["parsed"]["tools"][:8],
            "assistant_excerpt": (parallel_run["assistant"] or "")[:400],
        },
        "delta_wall_ms": int(serial_run["wall_ms"] or 0) - int(parallel_run["wall_ms"] or 0),
        "parallel_batch_observed": parallel_signal,
        "verdict": "PASS"
        if p2_pass and (parallel_signal or parallel_run["wall_ms"] <= serial_run["wall_ms"])
        else ("PARTIAL" if p2_pass else "FAIL"),
    }
    results["phases"]["phase2"] = p2
    write_json(OUT_DIR / "phase2-react-latency-live.json", {**p2, "recorded_at": utcnow()})

    # ── Phase 3 — plan visibility transcript ─────────────────────────
    p3_cid = new_conversation(token, org_id, "SOTA Phase 3 plan visibility")
    p3_run = chat(
        token,
        org_id,
        messages=[{"role": "user", "parts": [{"type": "text", "text": PLAN_PROMPT}]}],
        conversation_id=p3_cid,
    )
    steps = []
    for row in p3_run["parsed"]["intel"]:
        for s in row.get("progressSteps") or []:
            if s not in steps:
                steps.append(s)
    p3 = {
        "git_sha": git_sha,
        "conversation_id": p3_cid,
        "http": p3_run["http"],
        "plan_before_tools": p3_run["parsed"]["plan_before_tools"],
        "first_plan_idx": p3_run["parsed"]["first_plan_idx"],
        "first_tool_idx": p3_run["parsed"]["first_tool_idx"],
        "progress_steps": steps[:12],
        "event_order_head": p3_run["parsed"]["event_order"][:40],
        "transcript_head": p3_run["parsed"]["transcript"][:30],
        "assistant_excerpt": (p3_run["assistant"] or "")[:500],
        "verdict": "PASS"
        if p3_run["http"] == 200 and p3_run["parsed"]["plan_before_tools"]
        else ("PARTIAL" if p3_run["http"] == 200 and steps else "FAIL"),
    }
    results["phases"]["phase3"] = p3
    write_json(OUT_DIR / "phase3-plan-visibility-live.json", {**p3, "recorded_at": utcnow()})

    # ── Phase 4 — 30+ turns + continuity ─────────────────────────────
    p4_cid = new_conversation(token, org_id, "SOTA Phase 4 context scale")
    messages: list[dict[str, Any]] = []
    turn_log: list[dict[str, Any]] = []
    # Seed distinctive early facts, then filler turns, then recall.
    early_facts = [
        f"Remember for this project: primary account is {ENTITY_A} "
        f"and the pipeline codename is Orion-7. Confirm you stored that.",
        f"Secondary note: {ENTITY_B} is a competitor watchlist only — "
        "do not treat it as our account yet.",
    ]
    for i, text in enumerate(early_facts, start=1):
        messages.append({"role": "user", "parts": [{"type": "text", "text": text}]})
        run = chat(token, org_id, messages=messages, conversation_id=p4_cid)
        messages.append(
            {"role": "assistant", "parts": [{"type": "text", "text": run["assistant"] or "(ok)"}]}
        )
        turn_log.append({"turn": i, "http": run["http"], "wall_ms": run["wall_ms"]})
        if run["http"] != 200:
            stop_reason = f"Phase 4 early turn HTTP {run['http']}"
            break

    # Inflate history so summarization can fire (threshold ~80% of context window).
    filler = (
        "Context filler for compression proof. " * 40
        + "Retain prior account facts; do not invent new accounts. "
    )
    if not stop_reason:
        for i in range(3, 33):
            user_text = (
                f"Turn {i}: {filler} "
                f"Ack turn {i}. Keep {ENTITY_A} as primary unless I correct you."
            )
            messages.append({"role": "user", "parts": [{"type": "text", "text": user_text}]})
            # Cap outbound payload: keep last 40 messages in client body.
            outbound = messages[-40:]
            run = chat(token, org_id, messages=outbound, conversation_id=p4_cid)
            messages.append(
                {
                    "role": "assistant",
                    "parts": [{"type": "text", "text": (run["assistant"] or "(ok)")[:2000]}],
                }
            )
            turn_log.append({"turn": i, "http": run["http"], "wall_ms": run["wall_ms"]})
            if run["http"] != 200:
                stop_reason = f"Phase 4 turn {i} HTTP {run['http']}"
                break

    summary = load_summary(client, org_id, user_id, p4_cid)
    recall_text = (
        f"Without restating the filler, what is our primary account name "
        f"from the start of this conversation? Answer in one sentence."
    )
    messages.append({"role": "user", "parts": [{"type": "text", "text": recall_text}]})
    recall = chat(token, org_id, messages=messages[-40:], conversation_id=p4_cid)
    recalled = ENTITY_A.lower() in (recall["assistant"] or "").lower()
    turn_count = len([t for t in turn_log if t.get("http") == 200]) + (
        1 if recall["http"] == 200 else 0
    )
    p4 = {
        "git_sha": git_sha,
        "conversation_id": p4_cid,
        "successful_turns": turn_count,
        "turn_log_tail": turn_log[-6:],
        "last_summary_present": bool(summary) and not str(summary).startswith("__error__"),
        "last_summary_excerpt": (summary or "")[:500]
        if summary and not str(summary).startswith("__error__")
        else summary,
        "recall_http": recall["http"],
        "recall_mentions_entity_a": recalled,
        "recall_excerpt": (recall["assistant"] or "")[:500],
        "verdict": "PASS"
        if turn_count >= 30 and recalled and recall["http"] == 200
        else (
            "PARTIAL"
            if turn_count >= 30 and recall["http"] == 200
            else "FAIL"
        ),
    }
    results["phases"]["phase4"] = p4
    write_json(OUT_DIR / "phase4-context-scale-live.json", {**p4, "recorded_at": utcnow()})

    # ── Phase 5 — anti-repeat + correction ack ───────────────────────
    p5_cid = new_conversation(token, org_id, "SOTA Phase 5 voice")
    m5: list[dict[str, Any]] = [
        {
            "role": "user",
            "parts": [
                {
                    "type": "text",
                    "text": (
                        f"Briefly: is {ENTITY_A} Connected in our stack? "
                        "One short paragraph, then one next move."
                    ),
                }
            ],
        }
    ]
    r1 = chat(token, org_id, messages=m5, conversation_id=p5_cid)
    a1 = r1["assistant"] or ""
    m5.append({"role": "assistant", "parts": [{"type": "text", "text": a1}]})
    m5.append(
        {
            "role": "user",
            "parts": [
                {
                    "type": "text",
                    "text": (
                        "Same topic again — give the status update once more, "
                        "but do not reuse your previous wording verbatim."
                    ),
                }
            ],
        }
    )
    r2 = chat(token, org_id, messages=m5, conversation_id=p5_cid)
    a2 = r2["assistant"] or ""
    # Crude anti-repeat: longest common substring of 48+ chars should be absent.
    def longest_common(a: str, b: str, min_len: int = 48) -> str:
        a_n = re.sub(r"\s+", " ", a.strip().lower())
        b_n = re.sub(r"\s+", " ", b.strip().lower())
        best = ""
        for i in range(len(a_n)):
            for j in range(i + min_len, min(len(a_n), i + 160) + 1):
                sub = a_n[i:j]
                if sub in b_n and len(sub) > len(best):
                    best = sub
        return best

    overlap = longest_common(a1, a2)
    m5.append({"role": "assistant", "parts": [{"type": "text", "text": a2}]})
    m5.append({"role": "user", "parts": [{"type": "text", "text": CORRECTION_PROMPT}]})
    r3 = chat(token, org_id, messages=m5, conversation_id=p5_cid)
    a3 = r3["assistant"] or ""
    correction_ack_hit = bool(
        re.search(r"(?i)got it|updated to|continuing with", a3)
        and ENTITY_B.split()[0].lower() in a3.lower()
    )
    p5 = {
        "git_sha": git_sha,
        "conversation_id": p5_cid,
        "turn1_excerpt": a1[:400],
        "turn2_excerpt": a2[:400],
        "longest_verbatim_overlap": overlap[:120] if overlap else "",
        "anti_repeat_ok": not bool(overlap),
        "correction_prompt": CORRECTION_PROMPT,
        "correction_response_excerpt": a3[:500],
        "correction_ack_observed": correction_ack_hit,
        "verdict": "PASS"
        if r1["http"] == 200
        and r2["http"] == 200
        and r3["http"] == 200
        and correction_ack_hit
        and (not overlap or len(overlap) < 64)
        else (
            "PARTIAL"
            if r3["http"] == 200 and (correction_ack_hit or not overlap)
            else "FAIL"
        ),
    }
    results["phases"]["phase5"] = p5
    write_json(OUT_DIR / "phase5-voice-anti-repeat-live.json", {**p5, "recorded_at": utcnow()})

    results["finished_at"] = utcnow()
    results["stop_reason"] = stop_reason
    verdicts = [results["phases"][k]["verdict"] for k in ("phase2", "phase3", "phase4", "phase5")]
    if stop_reason:
        results["verdict"] = "STOP"
        code = 2
    elif all(v == "PASS" for v in verdicts):
        results["verdict"] = "PASS"
        code = 0
    elif any(v == "FAIL" for v in verdicts):
        results["verdict"] = "FAIL"
        code = 1
    else:
        results["verdict"] = "PARTIAL"
        code = 1
    write_json(OUT_DIR / "phases-2-5-sota-rollup-live.json", results)
    print(
        json.dumps(
            {
                "verdict": results["verdict"],
                "git_sha": git_sha,
                "phase_verdicts": {k: results["phases"][k]["verdict"] for k in results["phases"]},
                "governance": results["governance_probe"],
                "artifacts": [
                    "docs/delivery/phase2-react-latency-live.json",
                    "docs/delivery/phase3-plan-visibility-live.json",
                    "docs/delivery/phase4-context-scale-live.json",
                    "docs/delivery/phase5-voice-anti-repeat-live.json",
                    "docs/delivery/phases-2-5-sota-rollup-live.json",
                ],
            },
            indent=2,
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
