"""Which real turn shape actually reaches the query rewriter in production?

The first live attempt recorded zero `retrieval.query.rewritten` events: all
probe turns were served by unified-turn-live, which returns long before the
rewriter at `agent_intelligence.py:2610`. That is the same reachability trap
Phase B hit with the grounding validator, and it is a reachability finding, not
proof about the fix.

Production records four fallthrough reasons over 30 days (n=512):
    defer_classical_tool_sse         143
    outcome_error                    142
    pending_family_classical_resume  136
    read_tool_classical               91

Fallthrough is necessary but may not be sufficient — the connector-turn block
returns at line 2606, still ahead of the rewriter. So rather than reason about
which of the eight early returns fires for which shape, this sweeps several
shapes and lets the audit event decide.

Every scenario is TWO turns, because the rewriter returns early when there is no
conversation history; a one-shot question could never exercise it even on a
reachable path.
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

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "query-rewriter-reachable-shape.json"

# Reaching the rewriter needs a turn that BOTH carries conversation history AND
# falls through to the classical path. Earlier versions put the tool-shaped
# message first, so the turn that fell through was the one with no history (the
# rewriter then correctly declined before the model, and turns=0 gave it away).
# Here the SETUP is conversational — unified-turn-live serves it — and the
# FOLLOWUP is tool-shaped, forcing read_tool_classical on a turn that now has
# history and a pronoun that only history can resolve.
SHAPES = [
    {
        "label": "entity_then_tool_lookup",
        "mode": "standard",
        "setup": "Acme Corp is our largest mid-market account and their contract is up soon.",
        "followup": "look up their open deals in HubSpot",
    },
    {
        "label": "entity_then_tool_list",
        "mode": "standard",
        "setup": "We have been talking about Globex Industries as a renewal risk this quarter.",
        "followup": "pull their recent deals from HubSpot",
    },
    {
        "label": "person_then_tool_search",
        "mode": "standard",
        "setup": "Dana Whitfield is the main contact we have been dealing with at that account.",
        "followup": "search for her contact record in HubSpot",
    },
    {
        "label": "topic_then_tool_read",
        "mode": "standard",
        "setup": "The enterprise onboarding backlog has been the recurring problem all quarter.",
        "followup": "show me the deals related to that in HubSpot",
    },
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


def parse_sse(raw: str) -> str:
    texts: list[str] = []
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
    return "".join(texts).strip()


def events_since(sb: Any, action: str, since: str) -> list[dict[str, Any]]:
    return (
        sb.table("audit_events")
        .select("created_at,action,metadata")
        .eq("action", action)
        .gte("created_at", since)
        .order("created_at")
        .execute()
        .data
        or []
    )


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

    def _msg(role: str, text: str) -> dict[str, Any]:
        return {"role": role, "parts": [{"type": "text", "text": text}]}

    async def turn(
        client: httpx.AsyncClient,
        conv: str,
        text: str,
        mode: str,
        prior: list[dict[str, Any]] | None = None,
    ) -> str:
        # The server builds conversation_history from body.messages[:-1], NOT from
        # the database (assistant.py:1041). Posting only the current message left
        # the rewriter with no history, so it correctly declined before the model
        # and the earlier run misread that as the call failing to complete.
        body = {
            "messages": [*(prior or []), _msg("user", text)],
            "org_id": org_id,
            "mode": mode,
            "conversation_id": conv,
        }
        chunks: list[bytes] = []
        try:
            async with client.stream(
                "POST", f"{BASE}/api/assistant/chat", json=body, headers=headers, timeout=300.0
            ) as resp:
                async for c in resp.aiter_bytes():
                    chunks.append(c)
        except Exception as exc:  # noqa: BLE001
            print(f"    stream error: {exc}")
        return parse_sse(b"".join(chunks).decode("utf-8", "replace"))

    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        for sc in SHAPES:
            print(f"[{sc['label']}] mode={sc['mode']}")
            mark = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()

            r = await client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"qrs-{sc['label']}-{uuid.uuid4().hex[:6]}"},
                timeout=60,
            )
            r.raise_for_status()
            conv = str(r.json()["id"])

            setup_reply = await turn(client, conv, sc["setup"], sc["mode"])
            await asyncio.sleep(2)
            reply = await turn(
                client,
                conv,
                sc["followup"],
                sc["mode"],
                prior=[_msg("user", sc["setup"]), _msg("assistant", setup_reply or "(no reply)")],
            )
            await asyncio.sleep(6)

            rew = events_since(sb, "classical.answer_path.reached", mark)
            ft = events_since(sb, "unified_turn.live.fallthrough", mark)
            done = events_since(sb, "unified_turn.live.completed", mark)

            reasons = [
                str((e.get("metadata") or {}).get("fallthrough_reason") or "")
                for e in ft
            ]
            reached = len(rew) > 0
            print(f"  unified completed={len(done)} fallthrough={len(ft)} {reasons}")
            print(f"  region-reached events: {len(rew)}  -> entered region: {reached}")
            for e in rew:
                md = e.get("metadata") or {}
                print(
                    f"    mode={md.get('modeKey')} rewriteAttempted={md.get('rewriteAttempted')} "
                    f"modelRan={md.get('modelRan')} changed={md.get('changed')} "
                    f"turns={md.get('historyTurns')}"
                )
            print()

            results.append(
                {
                    "label": sc["label"],
                    "mode": sc["mode"],
                    "conversation_id": conv,
                    "setup": sc["setup"],
                    "followup": sc["followup"],
                    "assistant": reply[:400],
                    "unified_completed": len(done),
                    "unified_fallthrough": len(ft),
                    "fallthrough_reasons": reasons,
                    "rewrite_events": rew,
                    "reached_rewriter": reached,
                }
            )

    reached = [r for r in results if r["reached_rewriter"]]
    all_events = [e for r in results for e in r["rewrite_events"]]
    ran = [e for e in all_events if (e.get("metadata") or {}).get("modelRan")]
    changed = [e for e in all_events if (e.get("metadata") or {}).get("changed")]

    print("=== RESULT ===")
    print(f"shapes tried:                 {len(results)}")
    print(f"shapes reaching the rewriter: {len(reached)}")
    print(f"rewrite events total:         {len(all_events)}")
    print(f"  modelRan=true:              {len(ran)}")
    print(f"  changed the query:          {len(changed)}")

    if not reached:
        verdict = "UNREACHED"
        note = (
            "no turn shape tried reached the query rewriter. Like the grounding "
            "validator, it sits behind unified-turn-live on a path these shapes "
            "never take. The dormancy fix is correct but its production impact is "
            "unproven and may be small"
        )
    elif not ran:
        verdict = "FAIL"
        note = "the rewriter was reached but modelRan=false — the call still is not completing"
    else:
        verdict = "PASS"
        note = (
            f"{len(reached)}/{len(results)} shapes reached the rewriter and "
            f"{len(ran)}/{len(all_events)} events recorded modelRan=true, so the call "
            f"genuinely executes in production; {len(changed)} rewrote the query"
        )
    print(f"\n{verdict} — {note}")

    OUT.write_text(
        json.dumps(
            {
                "deployed_git_sha": git_sha,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "org_id": org_id,
                "verdict": verdict,
                "note": note,
                "shapes": results,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
