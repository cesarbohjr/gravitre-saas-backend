#!/usr/bin/env python3
"""Task-shaped unified-turn TTFT + light functional probes (not social).

Uses latency_breakdown instrumentation. Writes
docs/delivery/unified-turn-task-ttft-live.json

Probes with ``same_conversation_follow_up`` send a second user turn in the
same conversation to measure prefix-cache hit rate (turn 2 vs turn 1).
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
OUT = ROOT / "docs" / "delivery" / "unified-turn-task-ttft-live.json"
LABEL = os.environ.get("TTFT_LABEL", "baseline")

# Task-shaped / mixed only — no pure greetings.
PROBES = [
    {
        "id": "email_intent",
        "message": "Send an email to Stephanie about the proposal",
        "expect_live": True,
        "must_not_catalog": True,
        "same_conversation_follow_up": "Also CC the legal team on that email",
    },
    {
        "id": "apollo_list_write",
        "message": (
            f"Create an Apollo contact list named gravitre-task-ttft-{uuid.uuid4().hex[:6]}"
        ),
        "expect_awaiting_confirm": True,
    },
    {
        "id": "hubspot_search",
        "message": "Search HubSpot for Acme contacts",
        "expect_live": True,
    },
    {
        "id": "deals_status",
        "message": "How are the deals looking?",
        "expect_live": True,
        "same_conversation_follow_up": "Which deals are at risk this week?",
    },
    {
        "id": "mixed_hey_apollo",
        "message": "hey — also create an Apollo contact list named ConvPath TaskTTFT",
        "expect_not_pure_social": True,
    },
]

AUDIT_ACTIONS = [
    "unified_turn.live.completed",
    "unified_turn.shadow.completed",
    "unified_turn.live.fallthrough",
]


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


def _functional_ok(
    *,
    case: dict[str, Any],
    status: int,
    assistant: str,
    pending_status: str,
) -> bool:
    functional_ok = status == 200 and bool(assistant.strip())
    if case.get("expect_awaiting_confirm"):
        functional_ok = functional_ok and pending_status == "awaiting_confirm"
    if case.get("expect_not_pure_social"):
        functional_ok = functional_ok and bool(
            re.search(r"(?i)apollo|list|approval|yes|connect", assistant)
        )
    if case.get("must_not_catalog"):
        functional_ok = functional_ok and not re.search(
            r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){2,}\b",
            assistant,
            re.I,
        )
    return functional_ok


async def _fetch_turn_audit(
    *,
    sb: Any,
    org_id: str,
    cid: str,
    after: str,
) -> dict | None:
    for _ in range(20):
        rows = (
            sb.table("audit_events")
            .select("action,created_at,metadata")
            .eq("org_id", org_id)
            .eq("resource_id", cid)
            .in_("action", AUDIT_ACTIONS)
            .gte("created_at", after)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if rows.data:
            return rows.data[0]
        await asyncio.sleep(1)
    return None


async def _send_chat_turn(
    *,
    client: httpx.AsyncClient,
    headers: dict[str, str],
    org_id: str,
    cid: str,
    message: str,
    sb: Any,
    after: str,
) -> tuple[int, str, dict | None, dict[str, Any]]:
    status = 0
    assistant = ""
    async with client.stream(
        "POST",
        f"{BASE}/api/assistant/chat",
        headers=headers,
        json={
            "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
            "org_id": org_id,
            "mode": "standard",
            "conversation_id": cid,
        },
        timeout=300,
    ) as resp:
        status = resp.status_code
        chunks: list[bytes] = []
        async for part in resp.aiter_bytes():
            chunks.append(part)
        raw = b"".join(chunks).decode("utf-8", errors="replace")
        for block in raw.split("\n\n"):
            for ln in block.splitlines():
                if ln.startswith("data:"):
                    payload = ln[5:].strip()
                    if payload in ("", "[DONE]"):
                        continue
                    try:
                        o = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if o.get("type") == "text-delta":
                        assistant += str(o.get("delta") or "")

    await asyncio.sleep(2)
    audit = await _fetch_turn_audit(sb=sb, org_id=org_id, cid=cid, after=after)
    meta = _meta(audit)
    bd = meta.get("latency_breakdown") or {}
    if not isinstance(bd, dict):
        bd = {}
    return status, assistant, audit, meta


def _turn_metrics(meta: dict[str, Any]) -> dict[str, Any]:
    bd = meta.get("latency_breakdown") or {}
    if not isinstance(bd, dict):
        bd = {}
    return {
        "action": meta.get("action"),
        "created_at": meta.get("created_at"),
        "live_served": meta.get("live_served"),
        "outcome_kind": meta.get("outcome_kind"),
        "model": meta.get("model"),
        "first_token_proxy_ms": meta.get("first_token_proxy_ms"),
        "latency_breakdown": bd,
        "cached_prompt_tokens": bd.get("cached_prompt_tokens"),
        "cached_prompt_ratio": bd.get("cached_prompt_ratio"),
        "model_ttft_ms": bd.get("model_ttft_ms"),
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
        "feature": "unified_turn_task_ttft",
        "label": LABEL,
        "started_at": utcnow(),
        "probes": [],
        "same_conversation_cache": [],
    }

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        report["health"] = {
            k: health.get(k)
            for k in (
                "git_sha",
                "unified_turn_live_enabled",
                "timestamp",
            )
        }
        print("health", report["health"])

        wall: list[int] = []
        model: list[int] = []
        for case in PROBES:
            msg = case["message"]
            r = await client.post(
                f"{BASE}/api/conversations",
                headers=headers,
                json={"title": f"task-ttft-{case['id']}-{uuid.uuid4().hex[:6]}"},
                timeout=60,
            )
            r.raise_for_status()
            cid = str(r.json()["id"])
            after = utcnow()

            status, assistant, audit, meta = await _send_chat_turn(
                client=client,
                headers=headers,
                org_id=org_id,
                cid=cid,
                message=msg,
                sb=sb,
                after=after,
            )

            turn1 = _turn_metrics({**(audit or {}), **meta})
            bd = turn1.get("latency_breakdown") or {}
            ft = turn1.get("first_token_proxy_ms")
            mt = turn1.get("model_ttft_ms")
            cached_tok = turn1.get("cached_prompt_tokens")
            cached_ratio = turn1.get("cached_prompt_ratio")
            if isinstance(ft, (int, float)):
                wall.append(int(ft))
            if isinstance(mt, (int, float)):
                model.append(int(mt))

            conv = (
                sb.table("conversations")
                .select("task_state")
                .eq("id", cid)
                .eq("org_id", org_id)
                .limit(1)
                .execute()
            )
            pending = ((conv.data or [{}])[0].get("task_state") or {}).get("pending_task") or {}
            pending_status = str(pending.get("status") or "")

            functional_ok = _functional_ok(
                case=case,
                status=status,
                assistant=assistant,
                pending_status=pending_status,
            )

            turns: list[dict[str, Any]] = [
                {
                    "turn": 1,
                    "message": msg,
                    "http": status,
                    "action": (audit or {}).get("action"),
                    "created_at": (audit or {}).get("created_at"),
                    **{k: turn1[k] for k in turn1 if k not in {"latency_breakdown"}},
                    "assistant_preview": assistant[:280],
                    "functional_ok": functional_ok,
                }
            ]

            follow_up = case.get("same_conversation_follow_up")
            cache_compare: dict[str, Any] | None = None
            if follow_up:
                after2 = utcnow()
                status2, assistant2, audit2, meta2 = await _send_chat_turn(
                    client=client,
                    headers=headers,
                    org_id=org_id,
                    cid=cid,
                    message=str(follow_up),
                    sb=sb,
                    after=after2,
                )
                turn2 = _turn_metrics({**(audit2 or {}), **meta2})
                mt2 = turn2.get("model_ttft_ms")
                cached_tok2 = turn2.get("cached_prompt_tokens")
                cached_ratio2 = turn2.get("cached_prompt_ratio")
                if isinstance(turn2.get("first_token_proxy_ms"), (int, float)):
                    wall.append(int(turn2["first_token_proxy_ms"]))
                if isinstance(mt2, (int, float)):
                    model.append(int(mt2))

                turns.append(
                    {
                        "turn": 2,
                        "message": follow_up,
                        "http": status2,
                        "action": (audit2 or {}).get("action"),
                        "created_at": (audit2 or {}).get("created_at"),
                        **{k: turn2[k] for k in turn2 if k not in {"latency_breakdown"}},
                        "assistant_preview": assistant2[:280],
                    }
                )

                t1_mt = int(mt) if isinstance(mt, (int, float)) else None
                t2_mt = int(mt2) if isinstance(mt2, (int, float)) else None
                cache_compare = {
                    "probe_id": case["id"],
                    "conversation_id": cid,
                    "turn1": {
                        "cached_prompt_tokens": cached_tok,
                        "cached_prompt_ratio": cached_ratio,
                        "model_ttft_ms": t1_mt,
                    },
                    "turn2": {
                        "cached_prompt_tokens": cached_tok2,
                        "cached_prompt_ratio": cached_ratio2,
                        "model_ttft_ms": t2_mt,
                    },
                    "model_ttft_delta_ms": (
                        (t2_mt - t1_mt) if t1_mt is not None and t2_mt is not None else None
                    ),
                    "cached_ratio_delta": (
                        (float(cached_ratio2) - float(cached_ratio))
                        if cached_ratio is not None and cached_ratio2 is not None
                        else None
                    ),
                }
                report["same_conversation_cache"].append(cache_compare)
                print(json.dumps({"same_conversation_cache": cache_compare}))

            probe = {
                "id": case["id"],
                "conversation_id": cid,
                "http": status,
                "action": (audit or {}).get("action"),
                "created_at": (audit or {}).get("created_at"),
                "live_served": meta.get("live_served"),
                "outcome_kind": meta.get("outcome_kind"),
                "model": meta.get("model"),
                "first_token_proxy_ms": ft,
                "latency_breakdown": bd,
                "cached_prompt_tokens": cached_tok,
                "cached_prompt_ratio": cached_ratio,
                "pending_status": pending_status,
                "assistant_preview": assistant[:280],
                "functional_ok": functional_ok,
                "turns": turns,
                "same_conversation_cache": cache_compare,
            }
            report["probes"].append(probe)
            print(
                json.dumps(
                    {
                        "id": case["id"],
                        "wall": ft,
                        "model_ttft": mt,
                        "cached_prompt_tokens": cached_tok,
                        "cached_prompt_ratio": cached_ratio,
                        "retrieval": bd.get("retrieval_method") if isinstance(bd, dict) else None,
                        "visible": bd.get("visible_tools") if isinstance(bd, dict) else None,
                        "payload_b": bd.get("tools_payload_bytes") if isinstance(bd, dict) else None,
                        "model": meta.get("model"),
                        "functional_ok": functional_ok,
                        "turns": len(turns),
                    }
                )
            )

    if wall:
        report["wall_ttft_p50_ms"] = int(statistics.median(sorted(wall)))
        report["wall_ttft_min_ms"] = min(wall)
        report["wall_ttft_max_ms"] = max(wall)
    if model:
        report["model_ttft_p50_ms"] = int(statistics.median(sorted(model)))
        report["model_ttft_min_ms"] = min(model)
        report["model_ttft_max_ms"] = max(model)
    report["functional_pass_n"] = sum(1 for p in report["probes"] if p.get("functional_ok"))
    report["functional_n"] = len(report["probes"])
    report["ok"] = report["functional_pass_n"] == report["functional_n"]
    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    stamped = OUT.with_name(f"unified-turn-task-ttft-{LABEL}.json")
    stamped.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "label": LABEL,
                "wall_p50": report.get("wall_ttft_p50_ms"),
                "model_p50": report.get("model_ttft_p50_ms"),
                "functional": f"{report['functional_pass_n']}/{report['functional_n']}",
                "same_conversation_cache": report.get("same_conversation_cache"),
                "out": str(OUT),
                "stamped": str(stamped),
            },
            indent=2,
        )
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
