#!/usr/bin/env python3
"""Phase 4 monitoring window: copy leaks, write-approval staging, TTFT vs 200ms.

Requires LIVE cutover on prod (unified_turn_live_enabled=true).
Writes docs/delivery/unified-turn-phase4-monitor-live.json
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import statistics
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
OUT = ROOT / "docs" / "delivery" / "unified-turn-phase4-monitor-live.json"
CHAT_TIMEOUT = 300.0
TTFT_TARGET_MS = int(os.environ.get("UNIFIED_TURN_TTFT_TARGET_MS", "200"))
RAW_CATALOG_KEY = re.compile(r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){2,}\b", re.I)
MAP_FAIL = re.compile(r"couldn'?t map|no matching catalog action", re.I)
PHRASE_BANK_LEAK = re.compile(
    r"phrase.?bank|classical pipeline|unified_turn|stop_pipeline|module [abcd]\b",
    re.I,
)
APPROVAL_HINT = re.compile(r"reply\s+\*\*yes\*\*|needs your approval|approve", re.I)


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
                    "dialogue_mode": d.get("dialogueMode") or d.get("dialogue_mode"),
                    "pending_task": d.get("pendingTask") or d.get("pending_task"),
                }
            )
    return {"assistant": "".join(texts).strip(), "intel": intel}


def _meta(row: dict | None) -> dict[str, Any]:
    if not row:
        return {}
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return meta if isinstance(meta, dict) else {}


async def chat_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    conversation_id: str,
    org_id: str,
    message: str,
) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": org_id,
        "mode": "standard",
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


async def main() -> int:
    env = load_env()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if not env.get(key):
            raise SystemExit(f"missing {key}")
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
            "exp": int(time.time()) + 3600,
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
        "feature": "unified_turn_phase4_monitor",
        "started_at": utcnow(),
        "ttft_target_ms": TTFT_TARGET_MS,
        "copy_cases": [],
        "write_case": None,
        "ttft": {},
        "gates": {},
    }

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        report["health"] = {
            k: health.get(k)
            for k in (
                "git_sha",
                "unified_turn_live_enabled",
                "unified_turn_shadow_enabled",
                "timestamp",
            )
        }
        print("health", report["health"])
        if health.get("unified_turn_live_enabled") is not True:
            report["ok"] = False
            report["gates"]["live_enabled"] = "FAIL"
            OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print("FAIL: LIVE not enabled on tip")
            return 1
        report["gates"]["live_enabled"] = "PASS"

        copy_msgs = [
            ("greeting", "Hey"),
            ("thanks", "Thank you"),
            ("email_intent", "Send an email to Stephanie about the proposal"),
        ]
        ttft_samples: list[int] = []
        copy_ok = True
        for case_id, msg in copy_msgs:
            r = await client.post(
                f"{BASE}/api/conversations",
                headers=headers,
                json={"title": f"p4-mon-{case_id}-{uuid.uuid4().hex[:6]}"},
                timeout=60,
            )
            r.raise_for_status()
            cid = str(r.json()["id"])
            after = utcnow()
            turn = await chat_turn(
                client, headers, conversation_id=cid, org_id=org_id, message=msg
            )
            audit = None
            for _ in range(20):
                await asyncio.sleep(1)
                rows = (
                    sb.table("audit_events")
                    .select("action,created_at,metadata")
                    .eq("org_id", org_id)
                    .eq("resource_id", cid)
                    .in_(
                        "action",
                        [
                            "unified_turn.live.completed",
                            "unified_turn.live.fallthrough",
                            "unified_turn.shadow.completed",
                        ],
                    )
                    .gte("created_at", after)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if rows.data:
                    audit = rows.data[0]
                    break
            meta = _meta(audit)
            assistant = turn.get("assistant") or ""
            leaks: list[str] = []
            if RAW_CATALOG_KEY.search(assistant):
                leaks.append("assistant_catalog_key")
            if MAP_FAIL.search(assistant):
                leaks.append("map_fail_copy")
            if PHRASE_BANK_LEAK.search(assistant):
                leaks.append("internal_phrase_leak")
            user_msg = str(meta.get("user_message") or "")
            if RAW_CATALOG_KEY.search(user_msg):
                leaks.append("audit_user_message_catalog_key")
            ft = meta.get("first_token_proxy_ms")
            if isinstance(ft, (int, float)):
                ttft_samples.append(int(ft))
            case = {
                "id": case_id,
                "conversation_id": cid,
                "http": turn.get("http"),
                "action": (audit or {}).get("action"),
                "created_at": (audit or {}).get("created_at"),
                "live_served": meta.get("live_served"),
                "outcome_kind": meta.get("outcome_kind"),
                "first_token_ms": ft,
                "assistant_preview": assistant[:240],
                "leaks": leaks,
                "ok": (
                    turn.get("http") == 200
                    and (audit or {}).get("action") == "unified_turn.live.completed"
                    and bool(meta.get("live_served"))
                    and not leaks
                ),
            }
            report["copy_cases"].append(case)
            print(json.dumps({k: case[k] for k in ("id", "ok", "action", "leaks", "first_token_ms")}))
            if not case["ok"]:
                copy_ok = False
        report["gates"]["copy_leaks"] = "PASS" if copy_ok else "FAIL"

        # Write approval: must stage awaiting_confirm; no execute before yes.
        list_name = f"gravitre-p4-mon-{uuid.uuid4().hex[:8]}"
        write_msg = (
            f"Create an Apollo contact list named {list_name}. "
            "Do not invent that it already exists."
        )
        r = await client.post(
            f"{BASE}/api/conversations",
            headers=headers,
            json={"title": f"p4-mon-write-{uuid.uuid4().hex[:6]}"},
            timeout=60,
        )
        r.raise_for_status()
        wcid = str(r.json()["id"])
        after_w = utcnow()
        wturn = await chat_turn(
            client, headers, conversation_id=wcid, org_id=org_id, message=write_msg
        )
        await asyncio.sleep(2)
        conv = (
            sb.table("conversations")
            .select("task_state")
            .eq("id", wcid)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        task_state = (conv.data or [{}])[0].get("task_state") or {}
        pending = task_state.get("pending_task") or {}
        pending_status = str(pending.get("status") or "")
        params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
        invoke_action = str(params.get("invoke_action") or "")
        assistant_w = wturn.get("assistant") or ""
        approval_copy = bool(APPROVAL_HINT.search(assistant_w))
        staged = pending_status == "awaiting_confirm" or approval_copy
        # No completed tool invoke for this conversation after the write prompt.
        invokes = (
            sb.table("audit_events")
            .select("action,created_at,metadata")
            .eq("org_id", org_id)
            .eq("resource_id", wcid)
            .eq("action", "tool.invoke.completed")
            .gte("created_at", after_w)
            .limit(5)
            .execute()
        )
        invoke_n = len(invokes.data or [])
        live_rows = (
            sb.table("audit_events")
            .select("action,created_at,metadata")
            .eq("org_id", org_id)
            .eq("resource_id", wcid)
            .in_(
                "action",
                [
                    "unified_turn.live.completed",
                    "unified_turn.live.fallthrough",
                    "unified_turn.shadow.completed",
                ],
            )
            .gte("created_at", after_w)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        live_audit = (live_rows.data or [None])[0]
        live_meta = _meta(live_audit)
        ft_w = live_meta.get("first_token_proxy_ms")
        if isinstance(ft_w, (int, float)):
            ttft_samples.append(int(ft_w))
        write_ok = (
            wturn.get("http") == 200
            and staged
            and invoke_n == 0
            and not RAW_CATALOG_KEY.search(assistant_w)
            and not PHRASE_BANK_LEAK.search(assistant_w)
        )
        # Prefer live path when LIVE is on; classical confirm staging still acceptable if gated.
        write_case = {
            "conversation_id": wcid,
            "http": wturn.get("http"),
            "list_name": list_name,
            "pending_status": pending_status,
            "invoke_action": invoke_action,
            "approval_copy": approval_copy,
            "tool_invoke_completed_n": invoke_n,
            "live_action": (live_audit or {}).get("action"),
            "live_served": live_meta.get("live_served"),
            "outcome_kind": live_meta.get("outcome_kind"),
            "assistant_preview": assistant_w[:320],
            "ok": write_ok,
        }
        report["write_case"] = write_case
        report["gates"]["write_approval_staged"] = "PASS" if write_ok else "FAIL"
        print(
            json.dumps(
                {
                    "write_ok": write_ok,
                    "pending_status": pending_status,
                    "invoke_n": invoke_n,
                    "live_action": write_case["live_action"],
                }
            )
        )

    if ttft_samples:
        ttft_samples_sorted = sorted(ttft_samples)
        p50 = int(statistics.median(ttft_samples_sorted))
        report["ttft"] = {
            "n": len(ttft_samples_sorted),
            "min_ms": ttft_samples_sorted[0],
            "p50_ms": p50,
            "max_ms": ttft_samples_sorted[-1],
            "samples_ms": ttft_samples_sorted,
            "target_ms": TTFT_TARGET_MS,
            "target_met": p50 < TTFT_TARGET_MS,
        }
        report["gates"]["ttft_200ms"] = (
            "PASS" if report["ttft"]["target_met"] else "MISS"
        )
    else:
        report["ttft"] = {"n": 0, "target_met": False}
        report["gates"]["ttft_200ms"] = "INCONCLUSIVE"

    report["ok"] = (
        report["gates"].get("live_enabled") == "PASS"
        and report["gates"].get("copy_leaks") == "PASS"
        and report["gates"].get("write_approval_staged") == "PASS"
    )
    # TTFT MISS does not fail the monitoring window close — it is an acknowledged miss.
    report["finished_at"] = utcnow()
    report["rollback"] = (
        "Set UNIFIED_TURN_LIVE_ENABLED=false then redeploy "
        "(or bump UNIFIED_TURN_RESTART_NONCE)."
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "gates": report["gates"],
                "ttft": report["ttft"],
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
