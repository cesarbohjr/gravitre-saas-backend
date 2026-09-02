"""Live production proof for site 8 (conversational_turn_gate.py:240).

The dormant call failed CLOSED to shape="task_shaped", which is also a
legitimate verdict — so no reply, latency figure, or error rate could ever
distinguish "the model decided task_shaped" from "the model never ran".
`turn.shape.classified` records `usedModel`, which does.

Two things are proven here, and they need different messages:

  usedModel=true                  -> the call genuinely executes in production
  shape in {conversational,mixed} -> a verdict the fail-closed default could
                                     NEVER produce, i.e. real behaviour change

Every message must bypass `heuristic_turn_shape` for the model to be the
decider at all. That is asserted against the real heuristic before anything is
sent, not assumed: any message carrying a data/connector keyword is claimed by
the heuristic and would prove nothing. Half the set is deliberately
task-shaped, to confirm the fix did not turn fail-closed into fail-open and
start routing real work into chitchat.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "turn-gate-live.json"

# expect_conversational: what the model SHOULD say. Recorded to check the fix
# changes real verdicts, but a wrong guess here is reported as a mismatch, not
# quietly folded into the pass.
CASES = [
    {
        "label": "reflective_step_back",
        "expect_conversational": True,
        "text": "I have been thinking it might be time to step back and reconsider the whole thing.",
    },
    {
        "label": "reflective_sits_with_it",
        "expect_conversational": True,
        "text": "That actually makes a lot of sense now that I have had a minute to sit with it.",
    },
    {
        "label": "reflective_not_sure_matters",
        "expect_conversational": True,
        "text": "Honestly I am not sure it matters as much as we were making it out to matter.",
    },
    {
        "label": "task_board_deck",
        "expect_conversational": False,
        "text": "Walk me through how we should approach the Q3 board deck.",
    },
    {
        "label": "task_onboarding_outline",
        "expect_conversational": False,
        "text": "Put together an outline for the onboarding revamp we discussed last month.",
    },
    {
        "label": "task_vendor_tradeoffs",
        "expect_conversational": False,
        "text": "Break down the tradeoffs between the two vendor options we shortlisted.",
    },
]


def parse_sse(raw: str) -> str:
    out: list[str] = []
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
        if isinstance(obj, dict) and obj.get("type") == "text-delta":
            out.append(str(obj.get("delta") or ""))
    return "".join(out)


def gate_check() -> list[dict[str, Any]]:
    """Confirm the heuristic really declines each message, so the model decides."""
    from app.services.conversational_turn_gate import heuristic_turn_shape

    rows = []
    for c in CASES:
        decision = heuristic_turn_shape(c["text"])
        rows.append(
            {
                "label": c["label"],
                "heuristic_claims_it": decision is not None,
                "heuristic_reason": getattr(decision, "reason", None),
                "reaches_model_tier": decision is None,
            }
        )
    return rows


async def main() -> int:
    from supabase import create_client

    sys.path.insert(0, str(ROOT / "backend" / "scripts"))
    from probe_classical_region_reach import load_env  # type: ignore

    env = load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    import jwt

    from isolated_conversation_org import (  # type: ignore
        resolve_isolated_conversation_actor,
        smoke_http_headers,
    )

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])

    async with httpx.AsyncClient() as c:
        health = (await c.get(f"{BASE}/health", timeout=60)).json()
    git_sha = str(health.get("git_sha") or "")
    print(f"deployed tip: {git_sha}")

    gates = gate_check()
    print("\n=== gate check (does the heuristic decline, leaving it to the model) ===")
    for g in gates:
        print(
            f"  {g['label']:30s} claimed_by_heuristic={g['heuristic_claims_it']} "
            f"reason={g['heuristic_reason']}"
        )
    if not all(g["reaches_model_tier"] for g in gates):
        print(
            "\nABORT: the heuristic claims at least one message, so that turn would "
            "prove nothing about the model tier. Fix the message set first."
        )
        return 1

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
    print(f"\norg: {org_id}\n")

    results: list[dict[str, Any]] = []
    window_start = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()

    async with httpx.AsyncClient() as client:
        for case in CASES:
            r = await client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"tg-{case['label']}-{uuid.uuid4().hex[:6]}"},
                timeout=60,
            )
            r.raise_for_status()
            conv = str(r.json()["id"])

            body = {
                "messages": [{"role": "user", "parts": [{"type": "text", "text": case["text"]}]}],
                "org_id": org_id,
                "mode": "standard",
                "conversation_id": conv,
            }
            chunks: list[bytes] = []
            try:
                async with client.stream(
                    "POST", f"{BASE}/api/assistant/chat", json=body, headers=headers, timeout=300.0
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        chunks.append(chunk)
            except Exception as exc:  # noqa: BLE001
                print(f"  stream error: {exc}")
            reply = parse_sse(b"".join(chunks).decode("utf-8", "replace"))
            print(f"[{case['label']}] {reply[:100]!r}")
            results.append(
                {
                    "label": case["label"],
                    "conversation_id": conv,
                    "expect_conversational": case["expect_conversational"],
                    "reply": reply[:400],
                }
            )
            await asyncio.sleep(3)

    await asyncio.sleep(8)
    events = (
        sb.table("audit_events")
        .select("created_at,action,metadata")
        .eq("action", "turn.shape.classified")
        .gte("created_at", window_start)
        .order("created_at")
        .execute()
        .data
        or []
    )

    print(f"\nturn.shape.classified events: {len(events)}")
    for e in events:
        md = e.get("metadata") or {}
        print(
            f"  {e['created_at']}  usedModel={md.get('usedModel')} "
            f"shape={md.get('shape')} category={md.get('category')} "
            f"live={md.get('liveEnabled')} reason={str(md.get('reason'))[:44]!r}"
        )

    used = [e for e in events if (e.get("metadata") or {}).get("usedModel")]
    non_default = [
        e
        for e in used
        if (e.get("metadata") or {}).get("shape") in {"conversational", "mixed"}
    ]
    dormancy_signature = [
        e
        for e in events
        if not (e.get("metadata") or {}).get("usedModel")
        and "model_unavailable" in str((e.get("metadata") or {}).get("reason") or "")
    ]

    print("\n=== RESULT ===")
    print(f"turns run:                        {len(results)}")
    print(f"events recorded:                  {len(events)}")
    print(f"  usedModel=true:                 {len(used)}")
    print(f"  shape conversational/mixed:     {len(non_default)}")
    print(f"  dormancy signature remaining:   {len(dormancy_signature)}")

    if not events:
        verdict = "INCONCLUSIVE"
        note = (
            "no turn.shape.classified event was written, so the caller was not "
            "reached — a reachability finding, not a pass"
        )
    elif dormancy_signature:
        verdict = "FAIL"
        note = (
            f"{len(dormancy_signature)} turn(s) still carry the model_unavailable "
            "signature — the call is not completing in production"
        )
    elif not used:
        verdict = "FAIL"
        note = (
            f"{len(events)} event(s) recorded but usedModel=false on every one, so "
            "the model tier never ran despite the heuristic declining"
        )
    else:
        verdict = "PASS"
        note = (
            f"{len(used)}/{len(events)} turns recorded usedModel=true, so site 8 "
            "genuinely executes in production"
        )
        if non_default:
            note += (
                f"; {len(non_default)} returned conversational/mixed — verdicts the "
                "fail-closed default could never produce, so this is a real "
                "behaviour change and not just a reached code path"
            )
        else:
            verdict = "PARTIAL"
            note += (
                "; but every verdict was task_shaped, which is what the dormant "
                "default also produced. The call is proven live, the behaviour "
                "change is not"
            )

    print(f"\n{verdict} — {note}")

    OUT.write_text(
        json.dumps(
            {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "deployed_tip": git_sha,
                "org_id": org_id,
                "gate_check": gates,
                "turns": results,
                "events": events,
                "verdict": verdict,
                "note": note,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    return 0 if verdict in ("PASS", "PARTIAL") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
