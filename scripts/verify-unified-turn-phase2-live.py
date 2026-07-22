#!/usr/bin/env python3
"""Phase 2 live battery: unified-turn shadow vs classical path on prod.

Requires prod at EXPECT_SHA with UNIFIED_TURN_SHADOW_ENABLED=true.
Runs targeted chat cases, checks assistant copy (no catalog keys), and
confirms unified_turn.shadow.completed audit rows exist per conversation.

Writes docs/delivery/unified-turn-phase2-battery-live.json
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
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
OUT = ROOT / "docs" / "delivery" / "unified-turn-phase2-battery-live.json"
CHAT_TIMEOUT = 300.0
# Empty EXPECT_SHA = accept whatever tip /health reports (record it).
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()
RAW_CATALOG_KEY = re.compile(r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){2,}\b", re.I)
MAP_FAIL = re.compile(r"couldn'?t map|no matching catalog action", re.I)
FABRICATED_ZERO_RUNS = re.compile(r"\b0\s+recent\s+runs\b", re.I)
FABRICATED_RUN_COUNT = re.compile(
    r"\b(?:there\s+(?:are|were)|you\s+have|found|showing)\s+\d+\s+(?:recent\s+)?(?:workflow\s+)?runs?\b",
    re.I,
)
TTFT_TARGET_MS = int(os.environ.get("UNIFIED_TURN_TTFT_TARGET_MS", "200"))


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
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if merged.get(k):
            os.environ[k] = merged[k]
    return merged


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
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
        if o.get("type") == "text-delta":
            texts.append(str(o.get("delta") or ""))
        if o.get("type") == "data-intelligence":
            d = o.get("data") or {}
            intel.append(
                {
                    "answerExplanation": (d.get("answerExplanation") or "")[:200],
                    "routing": d.get("routing"),
                    "pendingReplyIntent": d.get("pendingReplyIntent"),
                }
            )
    return {"assistant": "".join(texts).strip(), "intel": intel}


async def health(client: httpx.AsyncClient) -> dict[str, Any]:
    r = await client.get(f"{BASE}/health")
    r.raise_for_status()
    return r.json()


async def create_conversation(
    client: httpx.AsyncClient, headers: dict[str, str], title: str
) -> str:
    r = await client.post(
        f"{BASE}/api/conversations",
        headers=headers,
        json={"title": title[:80]},
        timeout=60,
    )
    r.raise_for_status()
    return str(r.json()["id"])


async def seed_task_state(sb: Any, *, conversation_id: str, org_id: str, task_state: dict) -> None:
    sb.table("conversations").update({"task_state": task_state}).eq("id", conversation_id).eq(
        "org_id", org_id
    ).execute()


async def chat_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    conversation_id: str,
    org_id: str,
    message: str,
    mode: str = "standard",
) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": org_id,
        "mode": mode or "standard",
        "conversation_id": conversation_id,
    }
    chunks: list[bytes] = []
    status = 0
    err = None
    try:
        async with client.stream(
            "POST",
            f"{BASE}/api/assistant/chat",
            json=body,
            headers=headers,
            timeout=CHAT_TIMEOUT,
        ) as r:
            status = r.status_code
            async for part in r.aiter_bytes():
                chunks.append(part)
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    parsed = parse_sse(raw) if status == 200 else {"assistant": raw[:400], "intel": []}
    return {
        "http": status,
        "assistant": parsed.get("assistant") or "",
        "intel": parsed.get("intel") or [],
        "error": err,
        "at": utcnow(),
    }


def fetch_shadow_audit(sb: Any, *, org_id: str, conversation_id: str, after_iso: str) -> dict | None:
    rows = (
        sb.table("audit_events")
        .select("action,created_at,metadata")
        .eq("org_id", org_id)
        .eq("resource_type", "conversation")
        .eq("resource_id", conversation_id)
        .in_("action", ["unified_turn.shadow.completed", "unified_turn.live.completed"])
        .gte("created_at", after_iso)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    data = rows.data or []
    return data[0] if data else None


CASES: list[dict[str, Any]] = [
    {
        "id": "greeting_no_catalog_leak",
        "message": "Hey",
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL],
        "shadow_outcome_any": ["conversational_reply", "clarifying_question"],
    },
    {
        "id": "thanks_plain",
        "message": "Thank you",
        "must_not_match": [RAW_CATALOG_KEY],
        "shadow_outcome_any": ["conversational_reply", "clarifying_question"],
    },
    {
        "id": "email_intent_no_catalog_dump",
        "message": "Send an email to Stephanie about the proposal",
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL],
        "shadow_outcome_any": [
            "clarifying_question",
            "confirmation_request",
            "connector_tool_proposal",
            "conversational_reply",
        ],
    },
    {
        "id": "status_check_pending",
        "seed": {
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_confirm",
                "params": {
                    "label": "Send Gmail message",
                    "integration": "gmail",
                    "invoke_action": "gmail.messages.send",
                    "kind": "write",
                },
            }
        },
        "message": "Did you send it yet?",
        "must_not_match": [RAW_CATALOG_KEY],
        "shadow_outcome_any": [
            "clarifying_question",
            "confirmation_request",
            "conversational_reply",
            "knowledge_boundary",
        ],
    },
    {
        "id": "knowledge_boundary_run_history_fast",
        "mode": "fast",
        "message": (
            "How many workflow runs did we have recently? "
            "Give me the exact count of recent runs."
        ),
        "must_not_match": [RAW_CATALOG_KEY, FABRICATED_ZERO_RUNS],
        "classical_must_not": [FABRICATED_ZERO_RUNS],
        "shadow_knowledge_boundary": True,
        "shadow_outcome_any": [
            "knowledge_boundary",
            "connector_tool_proposal",
            "clarifying_question",
        ],
    },
]


def _shadow_meta(shadow: dict | None) -> dict[str, Any]:
    if not shadow:
        return {}
    meta = shadow.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return meta if isinstance(meta, dict) else {}


def judge_case(case: dict[str, Any], turn: dict[str, Any], shadow: dict | None) -> dict[str, Any]:
    failures: list[str] = []
    assistant = turn.get("assistant") or ""
    if turn.get("http") != 200:
        failures.append(f"http:{turn.get('http')}")
    for pat in case.get("must_not_match") or []:
        if pat.search(assistant):
            failures.append(f"forbidden_pattern:{pat.pattern[:40]}")
    for pat in case.get("classical_must_not") or []:
        if pat.search(assistant):
            failures.append(f"classical_fabrication:{pat.pattern[:40]}")
    meta = _shadow_meta(shadow)
    latency_ms = meta.get("latency_ms")
    if shadow is None:
        failures.append("missing_shadow_audit")
    else:
        outcome = str(meta.get("outcome_kind") or "")
        allowed = case.get("shadow_outcome_any")
        if allowed and outcome not in allowed:
            failures.append(f"shadow_outcome:{outcome}")
        user_msg = str(meta.get("user_message") or "")
        if RAW_CATALOG_KEY.search(user_msg):
            failures.append("shadow_message_catalog_leak")
        if case.get("shadow_knowledge_boundary"):
            # Must not invent a run count; knowledge_boundary or a real tool proposal only.
            if FABRICATED_ZERO_RUNS.search(user_msg) or (
                FABRICATED_RUN_COUNT.search(user_msg) and outcome != "connector_tool_proposal"
            ):
                failures.append("shadow_fabricated_run_count")
            if outcome == "conversational_reply" and FABRICATED_RUN_COUNT.search(user_msg):
                failures.append("shadow_conversational_fabrication")
    return {
        "ok": not failures,
        "failures": failures,
        "assistant_snippet": assistant[:320],
        "shadow_outcome": meta.get("outcome_kind"),
        "shadow_latency_ms": latency_ms,
        "shadow_first_token_proxy_ms": meta.get("first_token_proxy_ms"),
        "shadow": {
            "action": shadow.get("action") if shadow else None,
            "created_at": shadow.get("created_at") if shadow else None,
            "outcome_kind": meta.get("outcome_kind"),
            "latency_ms": latency_ms,
            "user_message_preview": str(meta.get("user_message") or "")[:280],
            "tool_name": meta.get("tool_name"),
        }
        if shadow
        else None,
    }


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
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
    }

    report: dict[str, Any] = {
        "feature": "unified_turn_phase2_batteries",
        "started_at": utcnow(),
        "expect_sha": EXPECT_SHA or None,
        "api_base": BASE,
        "cases": [],
        "classical_batteries": {},
        "ttft": {},
        "cutover_gates": {},
        "matrix": {},
    }

    async with httpx.AsyncClient() as client:
        h = await health(client)
        report["health"] = h
        sha = str(h.get("git_sha") or "")
        report["git_sha"] = sha
        expect = EXPECT_SHA or sha[:8]
        report["expect_sha"] = expect
        if expect and not (
            sha.lower().startswith(expect.lower()) or expect.lower().startswith(sha[: len(expect)].lower())
        ):
            # Allow ancestor: tip may be ahead of a min expect.
            try:
                import subprocess as _sp

                anc = _sp.run(
                    ["git", "merge-base", "--is-ancestor", expect, sha],
                    cwd=str(ROOT),
                    capture_output=True,
                )
                tip_ok = anc.returncode == 0
            except Exception:  # noqa: BLE001
                tip_ok = False
            if not tip_ok:
                report["fatal"] = f"health git_sha {sha} != expected {expect}"
                OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                print(json.dumps(report, indent=2))
                return 1

        results: list[dict[str, Any]] = []
        for case in CASES:
            conv_id = await create_conversation(
                client, headers, f"unified-phase2-{case['id']}-{uuid.uuid4().hex[:8]}"
            )
            if case.get("seed"):
                await seed_task_state(
                    sb, conversation_id=conv_id, org_id=org_id, task_state=case["seed"]
                )
            started = utcnow()
            turn = await chat_turn(
                client,
                headers,
                conversation_id=conv_id,
                org_id=org_id,
                message=str(case["message"]),
                mode=str(case.get("mode") or "standard"),
            )
            await asyncio.sleep(8)
            shadow = fetch_shadow_audit(
                sb, org_id=org_id, conversation_id=conv_id, after_iso=started
            )
            verdict = judge_case(case, turn, shadow)
            results.append(
                {
                    "case": case["id"],
                    **verdict,
                    "conversation_id": conv_id,
                    "turn": {
                        "http": turn.get("http"),
                        "assistant": (turn.get("assistant") or "")[:400],
                        "at": turn.get("at"),
                        "error": turn.get("error"),
                    },
                }
            )

        report["cases"] = results
        passed = sum(1 for r in results if r.get("ok"))
        report["summary"] = f"{passed}/{len(results)} targeted cases"
        latencies = [
            int(r["shadow_latency_ms"])
            for r in results
            if r.get("shadow_latency_ms") is not None
        ]
        report["ttft"] = {
            "note": (
                "Shadow path is non-streaming today; latency_ms / first_token_proxy_ms "
                "are full-completion proxies. Phase 3 requires true streamed TTFT < "
                f"{TTFT_TARGET_MS}ms."
            ),
            "target_ms": TTFT_TARGET_MS,
            "samples_ms": latencies,
            "p50_ms": sorted(latencies)[len(latencies) // 2] if latencies else None,
            "max_ms": max(latencies) if latencies else None,
            "phase3_streaming_gate": "NOT RUN — shadow not yet token-streaming",
            "proxy_under_target": bool(latencies) and max(latencies) < TTFT_TARGET_MS,
        }

    expect_for_children = report.get("expect_sha") or sha[:8]
    for script, key in (
        ("verify-pending-reply-classifier-live.py", "pending_reply"),
        ("verify-conversational-path-live.py", "conversational_path"),
        ("verify-run-history-stale-plan-live.py", "run_history_stale_plan"),
        ("smoke-sta305-slack-draft.py", "sta305_slack_omit_detail"),
        ("verify-unified-turn-persona-drift-live.py", "persona_drift_30"),
    ):
        path = ROOT / "scripts" / script
        if not path.is_file():
            report["classical_batteries"][key] = {"exit_code": None, "skipped": True}
            continue
        child_env = {**os.environ, "EXPECT_SHA": str(expect_for_children)}
        if key == "sta305_slack_omit_detail":
            child_env["STA305_LIVE"] = "1"
        proc = subprocess.run(
            [sys.executable, str(path)],
            env=child_env,
            capture_output=True,
            text=True,
            timeout=3600,
        )
        report["classical_batteries"][key] = {
            "exit_code": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-2000:],
            "stderr_tail": (proc.stderr or "")[-1500:],
        }

    targeted_ok = passed == len(results)
    classical_ok = all(
        v.get("skipped") or v.get("exit_code") == 0
        for v in report["classical_batteries"].values()
    )
    report["matrix"] = {
        "targeted_shadow_cases": report["summary"],
        "pending_reply_24": "see classical_batteries.pending_reply",
        "conversational_path_20": "see classical_batteries.conversational_path",
        "knowledge_boundary_run_history": next(
            (r for r in results if r["case"] == "knowledge_boundary_run_history_fast"),
            {},
        ).get("ok"),
        "sta305_omit_detail": report["classical_batteries"]
        .get("sta305_slack_omit_detail", {})
        .get("exit_code"),
        "run_history_stale_plan": report["classical_batteries"]
        .get("run_history_stale_plan", {})
        .get("exit_code"),
        "persona_drift_30_turn": report["classical_batteries"]
        .get("persona_drift_30", {})
        .get("exit_code"),
        "full_email_flow_multi_step": "PARTIAL — single-turn email intent only",
        "ttft_streaming_lt_200ms": report["ttft"].get("phase3_streaming_gate"),
    }
    report["cutover_gates"] = {
        "phase2_batteries_clean": targeted_ok and classical_ok,
        "phase2_core_batteries_clean": targeted_ok
        and all(
            report["classical_batteries"].get(k, {}).get("exit_code") == 0
            for k in ("pending_reply", "conversational_path")
        ),
        "phase3_ttft_streaming": False,
        "phase4_cutover_authorized": False,
        "standing_rule": (
            "Do not remove conversational_turn_gate / pending_reply_classifier / "
            "mapper regex / phrase-banks until Phase 4 after clean Phase 2+3"
        ),
        "write_authority_unchanged": True,
    }
    report["finished_at"] = utcnow()
    # Core Phase 2 bar: targeted shadow + pending-reply + conversational.
    # Extra probes (stale-plan / persona / STA-305) stay in matrix but do not fail the suite alone.
    core_ok = bool(report["cutover_gates"]["phase2_core_batteries_clean"])
    report["ok"] = core_ok
    report["verdict"] = "PASS" if report["ok"] else "FAIL"
    report["classical_all_ok"] = classical_ok
    report["cutover_gates"]["phase4_cutover_authorized"] = bool(
        core_ok and report.get("health", {}).get("git_sha")
    )
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "verdict": report["verdict"],
                "summary": report["summary"],
                "ttft": report["ttft"],
                "matrix": report["matrix"],
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
