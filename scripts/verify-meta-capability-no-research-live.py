#!/usr/bin/env python3
"""Phase 0/1 live probe: meta capability must not trigger web research.

Sends 'What can you help me with?' to Marketing Analyst (and variants),
checks unified-turn audit for internet_hit_count and usage_records research_lookups.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
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

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "conv_beh_live",
    ROOT / "scripts" / "verify-conversational-behavior-live.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
find_agent = _mod.find_agent
parse_assistant = _mod.parse_assistant

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
LABEL = (os.environ.get("META_NO_RESEARCH_LABEL") or "phase0").strip()
OUT = ROOT / "docs" / "delivery" / f"meta-capability-no-research-{LABEL}.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()

PROBES = [
    ("marketing", "What can you help me with?", ["SEO", "Marketing Analyst", "marketing"]),
    ("marketing", "what are you able to do?", ["SEO", "Marketing Analyst", "marketing"]),
    ("sales", "what tools do you have access to?", ["Sales Agent", "Sales", "sales"]),
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
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        h = await client.get(f"{BASE}/health", timeout=30.0)
        h.raise_for_status()
        tip = str(h.json().get("git_sha") or "")
        if EXPECT_SHA and not tip.lower().startswith(EXPECT_SHA.lower()):
            OUT.write_text(
                json.dumps({"verdict": "FAIL", "fatal": f"tip {tip} != {EXPECT_SHA}"}, indent=2),
                encoding="utf-8",
            )
            return 1

        # Historical COGS: research_lookups whose query text looks meta (best-effort via metadata)
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        hist = (
            sb.table("usage_records")
            .select("id,recorded_at,quantity,metadata,org_id")
            .eq("metric_type", "research_lookups")
            .eq("org_id", org_id)
            .gte("recorded_at", since)
            .order("recorded_at", desc=True)
            .limit(200)
            .execute()
            .data
            or []
        )
        meta_like = 0
        for row in hist:
            meta = row.get("metadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {}
            blob = json.dumps(meta).lower()
            if any(
                x in blob
                for x in (
                    "what can you help",
                    "what are you able",
                    "what tools do you",
                    "help me with",
                )
            ):
                meta_like += 1

        rows_out: list[dict[str, Any]] = []
        for tag, message, needles in PROBES:
            agent = find_agent(sb, org_id, *needles)
            if not agent:
                rows_out.append({"tag": tag, "message": message, "ok": False, "error": "agent_not_found"})
                continue
            started = datetime.now(timezone.utc).isoformat()
            cr = await client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"meta-no-research-{LABEL}-{uuid.uuid4().hex[:6]}"},
                timeout=60.0,
            )
            cr.raise_for_status()
            conv_id = str(cr.json()["id"])
            async with client.stream(
                "POST",
                f"{BASE}/api/assistant/chat",
                headers=headers,
                json={
                    "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
                    "org_id": org_id,
                    "mode": "standard",
                    "conversation_id": conv_id,
                    "agent_id": str(agent["id"]),
                },
                timeout=180.0,
            ) as r:
                chunks: list[bytes] = []
                async for part in r.aiter_bytes():
                    chunks.append(part)
                status = r.status_code
            assistant = parse_assistant(b"".join(chunks).decode("utf-8", errors="replace"))
            raw = b"".join(chunks).decode("utf-8", errors="replace")
            has_internet_section = "INTERNET RESEARCH" in raw or "internet_research" in raw.lower()
            # noise citations in assistant text
            noise = bool(
                re.search(
                    r"(?i)(usher|esl|google assistant|spotify|youtube\.com/watch)",
                    assistant or "",
                )
            )

            await asyncio.sleep(2.0)
            usage = (
                sb.table("usage_records")
                .select("id,recorded_at,quantity,metadata")
                .eq("org_id", org_id)
                .eq("metric_type", "research_lookups")
                .gte("recorded_at", started)
                .order("recorded_at", desc=True)
                .limit(5)
                .execute()
                .data
                or []
            )
            audit = (
                sb.table("audit_events")
                .select("created_at,action,metadata")
                .eq("org_id", org_id)
                .eq("resource_id", conv_id)
                .gte("created_at", started)
                .order("created_at", desc=True)
                .limit(8)
                .execute()
                .data
                or []
            )
            internet_hits = None
            audit_actions = []
            for a in audit:
                audit_actions.append(a.get("action"))
                meta = a.get("metadata") or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except json.JSONDecodeError:
                        meta = {}
                km = meta.get("unified_turn_knowledge_meta") or meta.get("knowledge_meta") or {}
                if isinstance(km, dict) and "internet_hit_count" in km:
                    internet_hits = km.get("internet_hit_count")
                if meta.get("internet_hit_count") is not None:
                    internet_hits = meta.get("internet_hit_count")
                # nested in outcome
                for key in ("knowledge", "unifiedTurnKnowledge", "knowledgeMeta"):
                    nested = meta.get(key)
                    if isinstance(nested, dict) and nested.get("internet_hit_count") is not None:
                        internet_hits = nested.get("internet_hit_count")

            billed = len(usage) > 0
            # PASS when no research lookup billed and no noise citations
            ok = (not billed) and (not noise) and status == 200 and bool(assistant)
            rows_out.append(
                {
                    "tag": tag,
                    "agent": agent.get("name"),
                    "agent_id": agent.get("id"),
                    "message": message,
                    "conversation_id": conv_id,
                    "http_status": status,
                    "assistant_preview": (assistant or "")[:280],
                    "research_lookups_billed": billed,
                    "usage_rows": [
                        {
                            "id": u.get("id"),
                            "recorded_at": u.get("recorded_at"),
                            "metadata": u.get("metadata"),
                        }
                        for u in usage
                    ],
                    "internet_hit_count_audit": internet_hits,
                    "audit_actions": audit_actions[:6],
                    "noise_citation_in_reply": noise,
                    "ok": ok,
                }
            )

    passed = sum(1 for r in rows_out if r.get("ok"))
    artifact = {
        "feature": "meta_capability_no_research",
        "label": LABEL,
        "checkedAt": utcnow(),
        "git_sha": tip,
        "org_id": org_id,
        "historical_meta_like_research_lookups_30d_org": meta_like,
        "historical_research_lookups_sampled": len(hist),
        "verdict": "PASS" if passed == len(rows_out) and rows_out else "FAIL",
        "passed": passed,
        "total": len(rows_out),
        "rows": rows_out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": artifact["verdict"],
                "git_sha": tip,
                "passed": passed,
                "total": len(rows_out),
                "historical_meta_like_research_lookups_30d_org": meta_like,
                "billed": [r.get("research_lookups_billed") for r in rows_out],
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if artifact["verdict"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception:
        import traceback

        traceback.print_exc()
        raise SystemExit(2) from None
