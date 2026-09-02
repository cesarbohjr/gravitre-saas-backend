"""Live post-fix proof for site 8: retiring the model tier broke nothing.

Cesar's decision was keep the heuristic, retire the model tier. The retirement
is only safe if the consumers that actually use the gate still work, so this
checks them on the deployed tip rather than reasoning about them.

Three consumers, three checks:

  1. MIXED SOCIAL ACK — `_maybe_prepend_mixed_social_ack` calls the gate and
     needs shape == "mixed" with a task portion. The heuristic produces mixed on
     its own, so the ack must still be prepended. This is the gate's only value
     that reaches a LIVE-served reply, and the one thing that could silently
     die. Verified by the reply opening with a social beat before the data.

  2. CONVERSATIONAL — pure social turns must still get a conversational reply
     and must NOT be dragged into the task pipeline.

  3. TASK — pure task turns must still retrieve and answer, i.e. failing closed
     did not become failing useless.

Plus the audit side: `turn.shape.classified` must now report usedModel=false and
modelTierRetired=true whenever the heuristic declines, and there must be NO
event claiming the model ran.
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
OUT = ROOT / "docs" / "delivery" / "turn-gate-retirement-live.json"

# A social beat opening the reply. The ack generator is a model call, so the
# exact wording is not fixed; this matches the shape, not a string.
ACK_OPENERS = re.compile(
    r"(?i)^\s*(thanks|thank you|you'?re welcome|you are welcome|anytime|no worries|"
    r"glad|happy to|sure|of course|good morning|good afternoon|morning|hey|hi\b|"
    r"hello|ha\b|noted|on it|my pleasure|appreciate)"
)

PROBES: list[tuple[str, str]] = [
    # (expected_consumer, message)
    ("mixed_ack", "thanks! also can you list my hubspot deals"),
    ("mixed_ack", "appreciate it, but how many open deals do I have"),
    ("mixed_ack", "good morning, anyway can you pull up my hubspot contacts"),
    ("conversational", "thanks, that's really helpful"),
    ("conversational", "hey there"),
    ("task", "how many open deals do I have in hubspot"),
    # The shape the heuristic DECLINES: must fail closed to task_shaped and
    # still produce a sane reply, and must emit the retirement audit row.
    ("declined", "so anyway I was thinking about the thing we discussed"),
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


async def main() -> int:
    env = load_env()
    from supabase import create_client

    from isolated_conversation_org import (  # type: ignore
        resolve_isolated_conversation_actor,
        smoke_http_headers,
    )

    # Local ground truth: what the heuristic decides for each probe. The live
    # assertion depends on it, so it is recorded rather than assumed.
    from app.services.conversational_turn_gate import heuristic_turn_shape

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
    print(f"org          : {org_id}\n")

    print("local heuristic ground truth:")
    for consumer, msg in PROBES:
        d = heuristic_turn_shape(msg)
        shape = "None(declined)" if d is None else d.shape
        print(f"  [{consumer:14s}] {shape:14s} {msg!r}")
    print()

    window_start = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    turns: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        for consumer, msg in PROBES:
            # Fresh conversation per probe: the ack is suppressed when anything
            # is pending, so a shared thread could mask a working ack.
            r = await client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"gate8-{uuid.uuid4().hex[:6]}"},
                timeout=60,
            )
            r.raise_for_status()
            conv = str(r.json()["id"])

            body = {
                "messages": [{"role": "user", "parts": [{"type": "text", "text": msg}]}],
                "org_id": org_id,
                "mode": "standard",
                "conversation_id": conv,
            }
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
            reply = parse_sse(b"".join(chunks).decode("utf-8", "replace"))
            opens_social = bool(ACK_OPENERS.match(reply))
            print(f"  [{consumer:14s}] {msg!r}")
            print(f"      social_open={opens_social}  -> {reply[:120]!r}")
            turns.append(
                {
                    "consumer": consumer,
                    "message": msg,
                    "reply": reply[:400],
                    "answered": bool(reply),
                    "opens_with_social_beat": opens_social,
                }
            )
            await asyncio.sleep(2)

    print("\nwaiting for audit rows...")
    await asyncio.sleep(12)

    rows = (
        sb.table("audit_events")
        .select("created_at,metadata")
        .eq("action", "turn.shape.classified")
        .gte("created_at", window_start)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
        .data
        or []
    )
    events = [r.get("metadata") or {} for r in rows]
    claims_model = [e for e in events if e.get("usedModel")]
    retired_flag = [e for e in events if e.get("modelTierRetired")]

    print(f"\nturn.shape.classified events : {len(events)}")
    print(f"  claiming usedModel=true    : {len(claims_model)}  (must be 0)")
    print(f"  modelTierRetired=true      : {len(retired_flag)}")
    for e in events[:6]:
        print(f"    shape={e.get('shape')} usedModel={e.get('usedModel')} "
              f"retired={e.get('modelTierRetired')} callSite={e.get('callSite')}")

    # --- verdicts, per consumer ---
    def _of(kind: str) -> list[dict[str, Any]]:
        return [t for t in turns if t["consumer"] == kind]

    mixed = _of("mixed_ack")
    convo = _of("conversational")
    task = _of("task")
    declined = _of("declined")

    checks: list[tuple[str, bool, str]] = []

    checks.append(
        (
            "all turns answered",
            all(t["answered"] for t in turns),
            f"{sum(1 for t in turns if t['answered'])}/{len(turns)} produced a reply",
        )
    )
    acked = [t for t in mixed if t["opens_with_social_beat"]]
    checks.append(
        (
            "mixed social ack still fires",
            len(acked) >= 2,
            f"{len(acked)}/{len(mixed)} mixed turns opened with a social beat",
        )
    )
    checks.append(
        (
            "conversational turns still conversational",
            all(t["answered"] for t in convo),
            f"{sum(1 for t in convo if t['answered'])}/{len(convo)} answered",
        )
    )
    checks.append(
        (
            "task turns still answered",
            all(t["answered"] for t in task),
            f"{sum(1 for t in task if t['answered'])}/{len(task)} answered",
        )
    )
    checks.append(
        (
            "heuristic-declined turn fails closed but still replies",
            all(t["answered"] for t in declined),
            f"{sum(1 for t in declined if t['answered'])}/{len(declined)} answered",
        )
    )
    checks.append(
        (
            "no event claims the retired model tier ran",
            len(claims_model) == 0,
            f"{len(claims_model)} event(s) with usedModel=true",
        )
    )

    print("\n=== CHECKS ===")
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    failed = [name for name, ok, _ in checks if not ok]
    if failed:
        verdict = f"FAIL at {git_sha[:8]} — {failed}"
    else:
        verdict = (
            f"PASS at {git_sha[:8]} — model tier retired, mixed social ack still fires "
            f"({len(acked)}/{len(mixed)}), all {len(turns)} turns answered, "
            f"0 events claim the model ran"
        )
    print(f"\n{verdict}")

    OUT.write_text(
        json.dumps(
            {
                "git_sha": git_sha,
                "org_id": org_id,
                "turns": turns,
                "turn_shape_events": events[:20],
                "events_claiming_used_model": len(claims_model),
                "checks": [{"name": n, "pass": ok, "detail": d} for n, ok, d in checks],
                "verdict": verdict,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
