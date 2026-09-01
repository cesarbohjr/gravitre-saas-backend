"""Live proof: does the HubSpot search dead end still happen in production?

Before the fix, `audit_events` showed 8 of 12 HubSpot deal invocations running
`hubspot.deals.list` (success) and 4 running `hubspot.deals.search` (failing with
`validation_error`: "requires filter_groups array"). Same read question, two
tools, one of which refused every criteria-less call.

The fix makes the four hubspot.*.search executors honour their advertised schema:
`query` builds the vendor filter, and a criteria-less search is served from the
list endpoint. Unit tests are mutation-proven, and by this program's own record
that is not evidence — three green mutation-proven suites accompanied three live
failures earlier in this same session.

So this measures production directly:
  1. run the read query that used to fail, repeatedly
  2. read `audit_events` for tool invocations in the window
  3. PASS requires zero `validation_error` on any hubspot.*.search, AND at least
     one `hubspot.deals.search` that actually completed — proving the new
     criteria-less path ran against the real vendor rather than merely not being
     chosen this time.

That second condition matters: a run where the model happened to pick
`deals.list` every time would show zero failures while proving nothing.
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
OUT = ROOT / "docs" / "delivery" / "hubspot-search-dead-end-live.json"

ORIGINAL = (
    "Show me the most recent deals in our HubSpot pipeline with their amounts and close dates."
)

CASES: list[tuple[str, str, int]] = [
    ("original_deals_read", ORIGINAL, 5),
    # Phrased to invite the search tool specifically, with no filter criteria —
    # the exact shape the executor used to refuse.
    ("search_shaped_no_criteria", "Search our HubSpot deals and show me what's there.", 3),
    # A real text criterion, so `query` has to become a vendor filter.
    ("search_with_query", "Search HubSpot deals for anything matching Acme.", 2),
]

DEAD_END_MARKERS = (
    "invalid parameters",
    "requires filter_groups",
    "check required fields",
)


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
    return {"assistant": "".join(texts).strip()}


def hubspot_invocations(sb: Any, since: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for act in ("tool.invoke.completed", "tool.invoke.failed", "tool.invoke.error"):
        page = (
            sb.table("audit_events")
            .select("created_at,action,metadata")
            .eq("action", act)
            .gte("created_at", since)
            .execute()
            .data
            or []
        )
        for row in page:
            meta = row.get("metadata") or {}
            target = str(meta.get("action") or "")
            if not target.startswith("hubspot."):
                continue
            rows.append(
                {
                    "audit_action": act,
                    "created_at": row["created_at"],
                    "target_action": target,
                    "error": meta.get("error"),
                    "error_code": meta.get("error_code"),
                    "latency_ms": meta.get("latency_ms"),
                }
            )
    return sorted(rows, key=lambda r: r["created_at"])


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
    attempts: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        for label, message, repeats in CASES:
            for i in range(repeats):
                await asyncio.sleep(0.5 if i % 2 else 4.0)
                r = await client.post(
                    f"{BASE}/api/conversations",
                    headers={k: v for k, v in headers.items() if k != "Accept"},
                    json={"title": f"hsdead-{label}-{i}-{uuid.uuid4().hex[:6]}"},
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
                reply = parsed["assistant"]
                low = reply.lower()
                dead_end = any(m in low for m in DEAD_END_MARKERS)
                # A real answer should name deals, not just avoid an error.
                answered = any(w in low for w in ("deal", "amount", "close", "pipeline"))

                rec = {
                    "label": label,
                    "iteration": i,
                    "message": message,
                    "conversation_id": conv,
                    "elapsed_ms": elapsed,
                    "dead_end_in_reply": dead_end,
                    "answered_with_deal_content": answered,
                    "assistant": reply[:400],
                }
                attempts.append(rec)
                flag = "  <-- DEAD END" if dead_end else ("" if answered else "  (no deal content)")
                print(f"  [{label}#{i}] {elapsed}ms{flag}")

    print("\nsettling before reading audit_events…")
    await asyncio.sleep(8)
    invocations = hubspot_invocations(sb, window_start)

    searches = [r for r in invocations if r["target_action"].endswith(".search")]
    failed_searches = [
        r
        for r in searches
        if r["audit_action"] != "tool.invoke.completed"
        or str(r.get("error_code") or "") == "validation_error"
    ]
    completed_searches = [r for r in searches if r not in failed_searches]

    print(f"\nhubspot tool invocations in window: {len(invocations)}")
    for r in invocations:
        state = "ok " if r["audit_action"] == "tool.invoke.completed" else "FAIL"
        print(f"  {state} {r['target_action']}  {r.get('error') or ''}")

    dead_ends = [a for a in attempts if a["dead_end_in_reply"]]
    answered = [a for a in attempts if a["answered_with_deal_content"]]

    print("\n=== RESULT ===")
    print(f"turns run:                          {len(attempts)}")
    print(f"replies containing the dead end:    {len(dead_ends)}")
    print(f"replies with real deal content:     {len(answered)}")
    print(f"hubspot.*.search invocations:       {len(searches)}")
    print(f"  completed:                        {len(completed_searches)}")
    print(f"  failed / validation_error:        {len(failed_searches)}")

    search_path_exercised = bool(completed_searches)
    verdict: str
    if dead_ends or failed_searches:
        verdict = "FAIL"
        note = "the dead end still occurs in production"
    elif not search_path_exercised:
        verdict = "INCONCLUSIVE"
        note = (
            "no hubspot.*.search invocation completed in this window, so the model "
            "never took the fixed path — absence of failure proves nothing here"
        )
    elif not answered:
        verdict = "INCONCLUSIVE"
        note = "no dead end, but no reply carried real deal content either"
    else:
        verdict = "PASS"
        note = (
            f"{len(completed_searches)} hubspot.*.search invocation(s) completed "
            f"against the real vendor with zero validation_error, and "
            f"{len(answered)}/{len(attempts)} turns answered with deal content"
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
                "turns": len(attempts),
                "dead_end_replies": len(dead_ends),
                "answered_replies": len(answered),
                "search_invocations": searches,
                "failed_searches": failed_searches,
                "all_hubspot_invocations": invocations,
                "attempts": attempts,
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
