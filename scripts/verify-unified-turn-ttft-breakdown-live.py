#!/usr/bin/env python3
"""TTFT investigation: instrumented breakdown + catalog size + classical baseline.

1) Hits prod chat (LIVE path) and reads latency_breakdown from audits.
2) Confirms tool retrieval method / payload sizes (not full 600+ catalog).
3) Times classical conversational path (heuristic + phrase bank — no tools LLM).

Writes docs/delivery/unified-turn-ttft-breakdown-live.json
"""
from __future__ import annotations

import asyncio
import json
import os
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
OUT = ROOT / "docs" / "delivery" / "unified-turn-ttft-breakdown-live.json"
PROBES = ["Hey", "Thank you", "What's on your plate?"]


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


def offline_catalog_probe(messages: list[str], *, max_tools: int = 32) -> dict[str, Any]:
    """Measure registry + keyword narrow payload sizes (no model call)."""
    from app.services.agent_platform_optimizer import narrow_tools_for_turn
    from app.services.tool_registry import get_tool_registry

    # Connected set assumed for payload sizing (common prod connectors).
    registry = get_tool_registry()
    connected = ["gmail", "apollo", "hubspot", "slack", "notion"]
    all_tools = registry.get_tools_for_agent(["*"], connected)
    rows = []
    for msg in messages:
        t0 = time.perf_counter()
        visible, stats = narrow_tools_for_turn(
            all_tools,
            query=msg,
            connected_integrations=connected,
            requires_action=None,
            max_tools=max_tools,
        )
        narrow_ms = int((time.perf_counter() - t0) * 1000)
        vis_bytes = len(json.dumps(visible, separators=(",", ":")).encode("utf-8"))
        full_bytes = len(json.dumps(all_tools, separators=(",", ":")).encode("utf-8"))
        rows.append(
            {
                "message": msg,
                "total_tools": len(all_tools),
                "visible_tools": len(visible),
                "max_tools_cap": max_tools,
                "visible_payload_bytes": vis_bytes,
                "full_catalog_payload_bytes": full_bytes,
                "narrow_ms": narrow_ms,
                "stats": stats,
                "retrieval_method": "keyword_narrow_tools_for_turn",
                "embedding_tool_retrieval": False,
            }
        )
    return {
        "connected_assumed": connected,
        "total_registered_for_connected": len(all_tools),
        "rows": rows,
        "note": (
            "Embedding-based tool retrieval is NOT implemented. "
            "Phase 0 chose keyword narrow_tools_for_turn (cap default 32)."
        ),
    }


async def classical_baseline_async(messages: list[str]) -> dict[str, Any]:
    from app.services.conversational_reply_service import generate_conversational_reply
    from app.services.conversational_turn_gate import (
        classify_turn_shape,
        heuristic_turn_shape,
        should_offer_conversational_path,
    )

    samples = []
    for msg in messages:
        t0 = time.perf_counter()
        heur = heuristic_turn_shape(msg)
        t_heur = time.perf_counter()
        decision = await classify_turn_shape(msg)
        t_class = time.perf_counter()
        offered = should_offer_conversational_path(decision, has_pending=False)
        reply = ""
        if offered:
            reply = await generate_conversational_reply(
                msg,
                decision=decision,
                task_state={},
                conversation_history=[],
                connected_integrations=["gmail", "apollo"],
                allow_humor=decision.category in {"banter", "greeting", "thanks"},
            )
        t_end = time.perf_counter()
        samples.append(
            {
                "message": msg,
                "heuristic_hit": heur is not None,
                "used_model_classify": bool(getattr(decision, "used_model", False)),
                "shape": decision.shape,
                "category": decision.category,
                "offered_conversational_path": offered,
                "reply_preview": (reply or "")[:120],
                "heuristic_ms": int((t_heur - t0) * 1000),
                "classify_ms": int((t_class - t0) * 1000),
                "total_ms": int((t_end - t0) * 1000),
                "path": (
                    "phrase_bank_no_llm"
                    if offered and heur is not None
                    else "classify_may_use_llm"
                ),
            }
        )
    totals = [s["total_ms"] for s in samples]
    return {
        "samples": samples,
        "p50_total_ms": int(statistics.median(totals)) if totals else None,
        "note": (
            "Fair baseline for Hey/Thank you: classical path is heuristic + phrase bank "
            "(no tool schemas, usually no LLM). Unified always pays a tool-aware model call."
        ),
    }


async def main() -> int:
    env = load_env()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if not env.get(key):
            raise SystemExit(f"missing {key}")
    # Ensure Settings() works for classical path / registry helpers.
    os.environ.setdefault("SUPABASE_ANON_KEY", env.get("SUPABASE_ANON_KEY") or env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or "offline-probe")
    for k in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_JWT_SECRET",
        "SUPABASE_ANON_KEY",
        "OPENAI_API_KEY",
    ):
        if env.get(k):
            os.environ[k] = env[k]

    report: dict[str, Any] = {
        "feature": "unified_turn_ttft_breakdown",
        "started_at": utcnow(),
        "catalog_offline": offline_catalog_probe(PROBES),
        "classical_baseline": await classical_baseline_async(PROBES),
        "unified_live": {"probes": [], "instrumentation_present": False},
    }

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

        wall_ttfTs: list[int] = []
        model_ttfTs: list[int] = []
        for msg in PROBES:
            r = await client.post(
                f"{BASE}/api/conversations",
                headers=headers,
                json={"title": f"ttft-bd-{uuid.uuid4().hex[:8]}"},
                timeout=60,
            )
            r.raise_for_status()
            cid = str(r.json()["id"])
            after = utcnow()
            t_client0 = time.perf_counter()
            first_sse_ms: int | None = None
            status = 0
            async with client.stream(
                "POST",
                f"{BASE}/api/assistant/chat",
                headers=headers,
                json={
                    "messages": [{"role": "user", "parts": [{"type": "text", "text": msg}]}],
                    "org_id": org_id,
                    "mode": "standard",
                    "conversation_id": cid,
                },
                timeout=300,
            ) as resp:
                status = resp.status_code
                async for chunk in resp.aiter_bytes():
                    if first_sse_ms is None and chunk:
                        first_sse_ms = int((time.perf_counter() - t_client0) * 1000)
            audit = None
            for _ in range(25):
                await asyncio.sleep(1)
                rows = (
                    sb.table("audit_events")
                    .select("action,created_at,metadata")
                    .eq("org_id", org_id)
                    .eq("resource_id", cid)
                    .in_(
                        "action",
                        ["unified_turn.live.completed", "unified_turn.shadow.completed"],
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
            bd = meta.get("latency_breakdown") or {}
            if bd:
                report["unified_live"]["instrumentation_present"] = True
            ft = meta.get("first_token_proxy_ms")
            if isinstance(ft, (int, float)):
                wall_ttfTs.append(int(ft))
            mt = bd.get("model_ttft_ms") if isinstance(bd, dict) else None
            if isinstance(mt, (int, float)):
                model_ttfTs.append(int(mt))
            probe = {
                "message": msg,
                "conversation_id": cid,
                "http": status,
                "client_first_sse_ms": first_sse_ms,
                "action": (audit or {}).get("action"),
                "created_at": (audit or {}).get("created_at"),
                "live_served": meta.get("live_served"),
                "first_token_proxy_ms": ft,
                "tool_stats": meta.get("tool_stats"),
                "latency_breakdown": bd,
            }
            report["unified_live"]["probes"].append(probe)
            print(
                json.dumps(
                    {
                        "msg": msg,
                        "wall_ttft": ft,
                        "model_ttft": bd.get("model_ttft_ms") if isinstance(bd, dict) else None,
                        "visible": (bd or {}).get("visible_tools")
                        if isinstance(bd, dict)
                        else (meta.get("tool_stats") or {}).get("visibleTools"),
                        "payload_b": (bd or {}).get("tools_payload_bytes")
                        if isinstance(bd, dict)
                        else None,
                        "retrieval": (bd or {}).get("retrieval_method")
                        if isinstance(bd, dict)
                        else None,
                    }
                )
            )

    if wall_ttfTs:
        report["unified_live"]["wall_ttft_p50_ms"] = int(statistics.median(sorted(wall_ttfTs)))
    if model_ttfTs:
        report["unified_live"]["model_ttft_p50_ms"] = int(statistics.median(sorted(model_ttfTs)))

    report["findings"] = {
        "full_catalog_sent_every_call": False,
        "retrieval": "keyword_narrow_tools_for_turn (NOT embedding)",
        "classical_social_uses_llm_tools": False,
        "ttft_200ms_gate": "MISS until model_ttft/payload work re-measured under target",
    }
    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(OUT), "instrumented": report["unified_live"]["instrumentation_present"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
