"""Live proof: does the tool-aware grounding validator judge tool answers correctly?

The first attempt at including agent mode (1e94e644) was reverted on measured
evidence: p50 9309ms added and 3 of 3 answers REPLACED, one landing on
SAFE_FALLBACK, because the validator could only see RAG chunks while agent-mode
answers come from tools.

The validator is now tool-aware. This drives real turns against the deployed tip
and checks the three things that decide whether inclusion survives this time:

  1. does the validator actually RUN on tool-answering turns (previously they
     were skipped as contextless, which is why coverage was zero)
  2. does it now PASS correct tool-derived answers instead of replacing them
     (the 3/3 replacement was the disqualifying failure)
  3. what latency does it really add

Honesty rules baked in:
  - a turn that produced no reply is a FAIL, not an absence of evidence
  - a reply equal to SAFE_FALLBACK is a FAIL even if no audit row says replaced
  - `assessorRan` false means the model fell through to the permissive default,
    so a "valid" verdict from it is not evidence the validator worked
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
OUT = ROOT / "docs" / "delivery" / "tool-aware-grounding-live.json"

SAFE_FALLBACK_MARKER = "not enough reliable context"

# Deliberately mixed, because evidenceKind is what is being proven.
# tool  -> connector data, the shape that was wrongly rejected before
# doc   -> knowledge retrieval, the shape that already worked
# none  -> conversational, must remain skipped and cost nothing
PROBES = [
    ("tool", "how many open deals do I have in hubspot right now"),
    ("tool", "list my hubspot contacts"),
    ("tool", "what are my most recent deals and their amounts"),
    ("doc", "what does our internal documentation say about refunds"),
    ("none", "thanks, that's helpful"),
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


def _pct(values: list[int], q: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(int(len(ordered) * q), len(ordered) - 1)]


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
    print(f"deployed tip : {git_sha}")
    print(f"org          : {org_id}")

    connectors = (
        sb.table("connectors")
        .select("vendor,status")
        .eq("org_id", org_id)
        .is_("deleted_at", "null")
        .execute()
        .data
        or []
    )
    active = [c for c in connectors if str(c.get("status") or "") == "connected"]
    print(f"connectors   : {len(active)} connected -> {[c.get('vendor') for c in active]}")
    print(
        "  (a connected connector is what upgrades standard/reasoning to agent,\n"
        "   which is the mode that had zero grounding coverage)\n"
    )

    window_start = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    turns: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"toolground-{uuid.uuid4().hex[:6]}"},
            timeout=60,
        )
        r.raise_for_status()
        conv = str(r.json()["id"])

        for kind, msg in PROBES:
            body = {
                "messages": [{"role": "user", "parts": [{"type": "text", "text": msg}]}],
                "org_id": org_id,
                "mode": "standard",
                "conversation_id": conv,
            }
            started = time.monotonic()
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
                print(f"  stream error: {exc}")
            elapsed = int((time.monotonic() - started) * 1000)
            reply = parse_sse(b"".join(chunks).decode("utf-8", "replace"))
            fallback = SAFE_FALLBACK_MARKER in reply.lower()
            flag = " <-- SAFE_FALLBACK" if fallback else ""
            print(f"  [{kind}] {msg!r}  ({elapsed}ms){flag}")
            print(f"      -> {reply[:130]!r}")
            turns.append(
                {
                    "kind": kind,
                    "message": msg,
                    "reply": reply[:400],
                    "answered": bool(reply),
                    "safe_fallback": fallback,
                    "wall_ms": elapsed,
                }
            )
            await asyncio.sleep(2)

    print("\nwaiting for audit rows to land...")
    await asyncio.sleep(12)

    rows = (
        sb.table("audit_events")
        .select("created_at,metadata")
        .eq("action", "answer.grounding.validated")
        .gte("created_at", window_start)
        .order("created_at", desc=True)
        .limit(200)
        .execute()
        .data
        or []
    )

    ran: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for r in rows:
        md = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
        (skipped if md.get("skipped") else ran).append({**md, "created_at": r.get("created_at")})

    durations = [int(e["durationMs"]) for e in ran if isinstance(e.get("durationMs"), (int, float))]
    tool_grounded = [e for e in ran if e.get("evidenceKind") in ("tool", "tool+doc")]
    replaced = [e for e in ran if e.get("answerReplaced")]
    assessor_ran = [e for e in ran if e.get("assessorRan")]

    print("\n=== answer.grounding.validated in window ===")
    print(f"total events          : {len(rows)}")
    print(f"  validator ran       : {len(ran)}")
    print(f"  skipped (no evidence): {len(skipped)}")
    print(f"  tool-grounded runs  : {len(tool_grounded)}")
    print(f"  assessor truly ran  : {len(assessor_ran)} of {len(ran)}")
    print(f"  answers replaced    : {len(replaced)} of {len(ran)}")

    if durations:
        print("\nvalidator latency on the real path:")
        print(f"  n={len(durations)}  p50={_pct(durations,0.50)}ms  "
              f"p95={_pct(durations,0.95)}ms  max={max(durations)}ms")

    if ran:
        print("\nper-run detail:")
        for e in ran[:14]:
            print(
                f"  {str(e.get('created_at',''))[:19]}  mode={e.get('modeKey'):<7} "
                f"evidence={str(e.get('evidenceKind')):<8} tools={e.get('toolResultCount')} "
                f"docs={e.get('ragSourceCount')} {e.get('durationMs')}ms "
                f"valid={e.get('isValid')} assessor={e.get('assessorRan')} "
                f"replaced={e.get('answerReplaced')} issues={e.get('issues')}"
            )
    if skipped:
        print("\nskipped detail:")
        for e in skipped[:8]:
            print(f"  {str(e.get('created_at',''))[:19]}  mode={e.get('modeKey')}  "
                  f"reason={e.get('skipReason')}")

    answered = [t for t in turns if t["answered"]]
    fallbacks = [t for t in turns if t["safe_fallback"]]

    # Verdict, most disqualifying condition first.
    if len(answered) < len(turns):
        verdict = (
            f"FAIL — only {len(answered)} of {len(turns)} turns replied; "
            "validator evidence does not count if turns did not run"
        )
    elif fallbacks:
        verdict = (
            f"FAIL — {len(fallbacks)} turn(s) landed on SAFE_FALLBACK: "
            f"{[t['message'] for t in fallbacks]}"
        )
    elif not ran:
        verdict = (
            "INCONCLUSIVE — no validator runs recorded. Either the mode gate did not "
            "open or no turn carried evidence; check skipped detail above"
        )
    elif not tool_grounded:
        verdict = (
            f"PARTIAL — validator ran {len(ran)}x but no run was tool-grounded, so the "
            "specific fix is unproven. Tool-answering turns may not have used tools."
        )
    elif replaced:
        verdict = (
            f"FAIL — {len(replaced)} of {len(ran)} answers still replaced "
            f"(previous attempt: 3 of 3). Issues: {[e.get('issues') for e in replaced]}"
        )
    elif not assessor_ran:
        verdict = (
            "INCONCLUSIVE — every run fell through to the permissive heuristic default "
            "(assessorRan=false), so no verdict came from the model"
        )
    else:
        verdict = (
            f"PASS — {len(tool_grounded)} tool-grounded run(s), {len(assessor_ran)}/{len(ran)} "
            f"judged by the model, 0 answers replaced, p50={_pct(durations,0.50)}ms "
            f"p95={_pct(durations,0.95)}ms at {git_sha[:8]}. Previous attempt at 1e94e644: "
            "3 of 3 replaced, p50 9309ms."
        )

    print(f"\n{verdict}")

    OUT.write_text(
        json.dumps(
            {
                "git_sha": git_sha,
                "org_id": org_id,
                "connectors_connected": [c.get("vendor") for c in active],
                "turns": turns,
                "events_total": len(rows),
                "validator_ran": len(ran),
                "skipped_no_evidence": len(skipped),
                "tool_grounded_runs": len(tool_grounded),
                "assessor_ran": len(assessor_ran),
                "answers_replaced": len(replaced),
                "durations_ms": durations,
                "p50_ms": _pct(durations, 0.50),
                "p95_ms": _pct(durations, 0.95),
                "ran_detail": ran[:20],
                "skipped_detail": skipped[:20],
                "baseline_1e94e644": {
                    "p50_ms": 9309,
                    "p95_ms": 10131,
                    "answers_replaced": "3 of 3",
                },
                "verdict": verdict,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
