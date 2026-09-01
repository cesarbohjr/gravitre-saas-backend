"""Does a read-only request ever produce a destructive write proposal?

One observed instance: "Show me the most recent deals in our HubSpot pipeline
with their amounts and close dates." left a pending `hubspot.lists.create`
(`destructive: true`, `requires_approval: true`) with args
`{"name": "MSPs", "object_type_id": "0-1", "processing_type": "MANUAL"}`.

Provenance of the args is already settled and is NOT contamination:
`inference_sources` marks all three `pack_common_default`, and "MSPs" is
`DEFAULT_HUBSPOT_LIST_NAME` applied by `apply_pack_common_defaults`. Those
defaults only run on a plan that is *already* `hubspot.lists.create`, so the
question this probe answers is the upstream one: can a read-only request select a
destructive create action at all?

Method: repeat the exact original query several times, plus read-only variants
that mention lists, HubSpot, or plural nouns that a list-create intent regex
might latch onto. After every turn, read `conversations.task_state.pending_task`
straight from the database and flag any destructive proposal.

A clean sweep does not prove the bug absent — it was seen once. It bounds the
rate, and the caller is expected to fall back to testing the mismatch net.
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

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "readonly-destructive-proposal-probe.json"

ORIGINAL = (
    "Show me the most recent deals in our HubSpot pipeline with their amounts and close dates."
)

# (label, message, repeats). The original is repeated most, since it is the only
# shape ever observed to misfire.
CASES: list[tuple[str, str, int]] = [
    ("original_deals_read", ORIGINAL, 4),
    (
        "readonly_lists_mention",
        "What contact lists do we currently have in HubSpot? Just show me, don't change anything.",
        2,
    ),
    (
        "readonly_plural_contacts",
        "Show me our HubSpot contacts from the last week.",
        2,
    ),
    (
        "readonly_pipeline_summary",
        "Summarize the state of our HubSpot pipeline for me.",
        2,
    ),
]


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (ROOT / "backend" / ".env", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
    return merged


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    pending: Any = None
    for block in re.split(r"\n\n+", raw):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "text-delta":
            texts.append(str(obj.get("delta") or ""))
        data = obj.get("data") if isinstance(obj.get("data"), dict) else obj
        if isinstance(data, dict) and data.get("pendingTask") or (
            isinstance(data, dict) and data.get("pending_task")
        ):
            pending = data.get("pendingTask") or data.get("pending_task")
    return {"assistant": "".join(texts).strip(), "pending_in_sse": pending}


def destructive_pending(sb: Any, conv_id: str) -> tuple[bool, dict[str, Any] | None]:
    rows = (
        sb.table("conversations").select("task_state").eq("id", conv_id).limit(1).execute().data
        or []
    )
    if not rows:
        return False, None
    pt = (rows[0].get("task_state") or {}).get("pending_task")
    if not isinstance(pt, dict):
        return False, None
    params = pt.get("params") or {}
    is_destructive = bool(params.get("destructive")) or bool(params.get("requires_approval"))
    return is_destructive, pt


async def main() -> int:
    env = load_env()
    from supabase import create_client

    from isolated_conversation_org import (  # type: ignore
        resolve_isolated_conversation_actor,
        smoke_http_headers,
    )

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

    git_sha = str(httpx.get(f"{BASE}/health", timeout=30).json().get("git_sha") or "")
    print(f"deployed tip: {git_sha}\norg: {org_id}\n")

    attempts: list[dict[str, Any]] = []
    hits: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        for label, message, repeats in CASES:
            for i in range(repeats):
                # Vary timing: alternate a cold gap with a rapid follow-on, since
                # the one observed misfire happened inside a fast scripted burst.
                gap = 0.5 if i % 2 else 6.0
                await asyncio.sleep(gap)

                r = await client.post(
                    f"{BASE}/api/conversations",
                    headers={k: v for k, v in headers.items() if k != "Accept"},
                    json={"title": f"rdprobe-{label}-{i}-{uuid.uuid4().hex[:6]}"},
                    timeout=60,
                )
                r.raise_for_status()
                conv = str(r.json()["id"])

                body = {
                    "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
                    "org_id": org_id,
                    "mode": "standard",
                    "conversation_id": conv,
                }
                t0 = time.perf_counter()
                chunks: list[bytes] = []
                try:
                    async with client.stream(
                        "POST",
                        f"{BASE}/api/assistant/chat",
                        json=body,
                        headers=headers,
                        timeout=300.0,
                    ) as resp:
                        async for c in resp.aiter_bytes():
                            chunks.append(c)
                except Exception as exc:  # noqa: BLE001
                    print(f"  [{label}#{i}] stream error: {exc}")
                parsed = parse_sse(b"".join(chunks).decode("utf-8", "replace"))
                elapsed = int((time.perf_counter() - t0) * 1000)

                await asyncio.sleep(3)
                is_destructive, pt = destructive_pending(sb, conv)
                params = (pt or {}).get("params") or {}
                rec = {
                    "label": label,
                    "iteration": i,
                    "gap_before_s": gap,
                    "message": message,
                    "conversation_id": conv,
                    "elapsed_ms": elapsed,
                    "pending_present": pt is not None,
                    "pending_destructive": is_destructive,
                    "pending_action": params.get("invoke_action") or params.get("tool_name"),
                    "pending_args": params.get("args"),
                    "assistant": parsed["assistant"][:300],
                }
                attempts.append(rec)
                if is_destructive:
                    hits.append(rec)

                flag = "  <-- DESTRUCTIVE PROPOSAL" if is_destructive else ""
                print(
                    f"  [{label}#{i}] gap={gap}s {elapsed}ms "
                    f"pending={rec['pending_action'] or 'none'}{flag}"
                )

    total = len(attempts)
    result = {
        "deployed_git_sha": git_sha,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "org_id": org_id,
        "original_query": ORIGINAL,
        "attempts_total": total,
        "destructive_proposals": len(hits),
        "hits": hits,
        "attempts": attempts,
        "finding": (
            f"REPRODUCED — {len(hits)}/{total} read-only turns produced a destructive proposal"
            if hits
            else f"NOT REPRODUCED in {total} deliberate attempts"
        ),
    }
    OUT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nattempts: {total}   destructive proposals: {len(hits)}")
    print(f"FINDING: {result['finding']}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
