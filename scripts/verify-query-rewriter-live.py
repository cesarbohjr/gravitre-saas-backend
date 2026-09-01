"""Live proof: is the re-enabled retrieval query rewriter (site 7) running in production?

The local before/after proves the router is entered now and was not before. What
it cannot show is production behaviour, because this environment has no AI
provider credentials.

This site is unusually easy to prove honestly, because the fix ships with a
`retrieval.query.rewritten` audit event whose `modelRan` field is set only after
`router.complete` returns. That directly separates the two states which are
otherwise byte-identical in the returned query:

    modelRan=false  -> the call did not complete (the dormancy signature)
    modelRan=true   -> the model genuinely ran, whether or not it rewrote

Method: open a conversation, establish an entity in turn 1, then ask a follow-up
whose meaning depends entirely on that turn ("and what about their renewal?").
Read the audit events for the follow-up turn.

The caller is gated on `mode_key != "fast"`, so the probe uses a mode that
reaches it, and reports honestly if no event is written at all — that would mean
the path is not reached, which is a different finding from the call being
dormant, and must not be reported as a pass.
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
OUT = ROOT / "docs" / "delivery" / "query-rewriter-live.json"

# Turn 1 names the entity. Turn 2 is meaningless on its own: "their" has no
# referent in its own text, so a rewriter that is genuinely running has to pull
# the entity forward from turn 1.
SCENARIOS = [
    {
        "label": "pronoun_followup",
        "setup": "Tell me about the Acme Corp account and what plan they are on.",
        "followup": "and what about their renewal?",
        "entity": "acme",
    },
    {
        "label": "elliptical_followup",
        "setup": "Summarize our current onboarding process for new enterprise customers.",
        "followup": "how long does that usually take?",
        "entity": "onboarding",
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


def rewrite_events(sb: Any, since: str) -> list[dict[str, Any]]:
    rows = (
        sb.table("audit_events")
        .select("created_at,action,metadata")
        .eq("action", "retrieval.query.rewritten")
        .gte("created_at", since)
        .order("created_at")
        .execute()
        .data
        or []
    )
    return rows


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
    window_start = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()

    async def turn(client: httpx.AsyncClient, conv: str, text: str) -> str:
        body = {
            "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
            "org_id": org_id,
            "mode": "standard",
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
        for sc in SCENARIOS:
            print(f"[{sc['label']}]")
            r = await client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"qr-{sc['label']}-{uuid.uuid4().hex[:6]}"},
                timeout=60,
            )
            r.raise_for_status()
            conv = str(r.json()["id"])

            print(f"  turn 1 (establish entity): {sc['setup'][:60]}…")
            await turn(client, conv, sc["setup"])
            await asyncio.sleep(2)

            print(f"  turn 2 (context-dependent): {sc['followup']!r}")
            reply = await turn(client, conv, sc["followup"])
            await asyncio.sleep(3)

            results.append(
                {
                    "label": sc["label"],
                    "conversation_id": conv,
                    "setup": sc["setup"],
                    "followup": sc["followup"],
                    "assistant": reply[:500],
                }
            )
            print(f"  reply: {reply[:140]!r}\n")

    await asyncio.sleep(8)
    events = rewrite_events(sb, window_start)

    print(f"retrieval.query.rewritten events in window: {len(events)}")
    ran = [e for e in events if (e.get("metadata") or {}).get("modelRan")]
    changed = [e for e in events if (e.get("metadata") or {}).get("changed")]
    for e in events:
        md = e.get("metadata") or {}
        print(
            f"  {e['created_at']}  modelRan={md.get('modelRan')} "
            f"changed={md.get('changed')} mode={md.get('modeKey')} "
            f"turns={md.get('historyTurns')} {md.get('originalChars')}→{md.get('refinedChars')} chars"
        )

    print("\n=== RESULT ===")
    print(f"turns run:                      {len(results)}")
    print(f"rewrite events recorded:        {len(events)}")
    print(f"  with modelRan=true:           {len(ran)}")
    print(f"  that actually changed query:  {len(changed)}")

    if not events:
        verdict = "INCONCLUSIVE"
        note = (
            "no retrieval.query.rewritten event was written at all, so the caller was "
            "never reached on these turns. That is a reachability finding, not proof "
            "the call works or fails — the same trap Phase B hit with the grounding "
            "validator, and it is not being rounded up to a pass"
        )
    elif not ran:
        verdict = "FAIL"
        note = (
            f"{len(events)} rewrite event(s) recorded and modelRan=false on every one — "
            "the model call still is not completing in production"
        )
    else:
        verdict = "PASS"
        note = (
            f"{len(ran)}/{len(events)} rewrite events recorded modelRan=true, so the "
            f"call genuinely executes in production; {len(changed)} produced a "
            f"different retrieval query than the user's raw text"
        )
        if not changed:
            verdict = "PARTIAL"
            note = (
                f"{len(ran)}/{len(events)} events show modelRan=true, so the dormancy is "
                "closed, but no turn produced a changed query — the capability runs "
                "without yet being shown to improve the retrieval query"
            )

    print(f"\n{verdict} — {note}")

    OUT.write_text(
        json.dumps(
            {
                "deployed_git_sha": git_sha,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "org_id": org_id,
                "site": "backend/app/services/query_rewriter.py:52",
                "verdict": verdict,
                "note": note,
                "events": events,
                "turns": results,
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
