"""Live production proof for sites 9 and 10.

Site 9  contextual_understanding_service.py:225  (goal/constraint extraction)
Site 10 domain_intelligence_service.py:208       (the "LLM fallback last" tier)

Both were dormant with no production signal whatsoever: an empty goal and a
low-confidence domain look identical whether the model ran or threw a TypeError.
`context.understanding.extracted` now records what separates them.

    modelRan=false while modelAttempted=true  -> the dormancy signature
    modelRan=true                             -> the call genuinely executes
    domainSource="llm"                        -> site 10's tier genuinely ran

Site 9's caller sits at agent_intelligence.py:1753, at function-body level, so it
runs on every streaming turn past the cache and pending-clarify returns. That
means — unlike the rewriter — this needs no exotic turn shape, only a message
that trips the gate: longer than 12 words and NOT ending in "?", since a
question is answered by the rule path before the model is consulted.

Reports honestly if no event is written at all: that is a reachability finding,
not a pass.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
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
OUT = ROOT / "docs" / "delivery" / "understanding-domain-live.json"

# Every message: >12 words, no trailing "?", so _infer_goal_from_rules returns
# None and the model tier is genuinely consulted. Verified against the real gate
# rather than assumed.
CASES = [
    {
        "label": "long_statement_renewals",
        "text": (
            "we need to tighten up the renewal motion for our mid market accounts "
            "before the quarter closes and make sure nothing slips through the cracks"
        ),
    },
    {
        "label": "ambiguous_domain_statement",
        "text": (
            "the handoff between the two teams keeps dropping things and i want to "
            "understand where exactly it breaks down before we change any process"
        ),
    },
    {
        "label": "multi_constraint_statement",
        "text": (
            "put together an approach for the enterprise segment that stays within "
            "our current headcount and does not require any new tooling spend this year"
        ),
    },
    # The three above all scored 0.7-0.8 on keyword rules, so they never reach
    # site 10's tier. These score 0.000 against the real rule classifier
    # (backend/scripts/scratch_pick_low_domain_confidence.py) — measured, not
    # guessed — which is the only condition under which the LLM tier runs.
    {
        "label": "low_domain_signal_unresolved",
        "text": (
            "the thing we talked about before still feels unresolved and i would like "
            "to get to the bottom of it sometime this week"
        ),
    },
    {
        "label": "low_domain_signal_pattern",
        "text": (
            "there is a pattern here that keeps coming back around again and i want to "
            "really understand why it happens at all"
        ),
    },
    {
        "label": "low_domain_signal_settle",
        "text": (
            "we keep going back and forth on this one and i would rather settle it "
            "properly than keep revisiting it every single time"
        ),
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


def gate_check() -> list[dict[str, Any]]:
    """Confirm each message really does bypass the rule path, not assume it."""
    from app.services.contextual_understanding_service import ContextualUnderstandingService

    rows = []
    for c in CASES:
        text = c["text"]
        rule_goal = ContextualUnderstandingService._can_infer_goal_from_rules(text)
        rows.append(
            {
                "label": c["label"],
                "words": len(text.split()),
                "ends_with_question": text.strip().endswith("?"),
                "rule_path_would_answer": bool(rule_goal),
                "reaches_model_tier": (not rule_goal) and len(text.split()) > 8,
            }
        )
    return rows


async def main() -> int:
    from dotenv import dotenv_values  # noqa: F401
    from supabase import create_client

    sys.path.insert(0, str(ROOT / "backend" / "scripts"))
    from probe_classical_region_reach import load_env  # type: ignore

    env = load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    import time

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
    print("\n=== gate check (does each message reach the model tier at all) ===")
    for g in gates:
        print(
            f"  {g['label']:32s} words={g['words']:3d} "
            f"rule_would_answer={g['rule_path_would_answer']} "
            f"reaches_model={g['reaches_model_tier']}"
        )
    if not all(g["reaches_model_tier"] for g in gates):
        print("\nABORT: at least one message is answered by the rule path, so it "
              "would prove nothing about the model tier.")
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
                json={"title": f"ud-{case['label']}-{uuid.uuid4().hex[:6]}"},
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
            print(f"[{case['label']}] reply: {reply[:110]!r}")
            results.append({"label": case["label"], "conversation_id": conv, "reply": reply[:400]})
            await asyncio.sleep(3)

    await asyncio.sleep(8)
    events = events_since(sb, "context.understanding.extracted", window_start)

    print(f"\ncontext.understanding.extracted events: {len(events)}")
    for e in events:
        md = e.get("metadata") or {}
        print(
            f"  {e['created_at']}  attempted={md.get('modelAttempted')} "
            f"ran={md.get('modelRan')} goal={md.get('goalPresent')} "
            f"constraints={md.get('constraintCount')} "
            f"domainSource={md.get('domainSource')} "
            f"conf={md.get('domainConfidence')} routing={md.get('domainRoutingActive')}"
        )

    attempted = [e for e in events if (e.get("metadata") or {}).get("modelAttempted")]
    ran = [e for e in attempted if (e.get("metadata") or {}).get("modelRan")]
    with_goal = [e for e in ran if (e.get("metadata") or {}).get("goalPresent")]
    llm_domain = [e for e in events if (e.get("metadata") or {}).get("domainSource") == "llm"]

    print("\n=== RESULT ===")
    print(f"turns run:                    {len(results)}")
    print(f"events recorded:              {len(events)}")
    print(f"  modelAttempted=true:        {len(attempted)}")
    print(f"  modelRan=true (site 9):     {len(ran)}")
    print(f"    of those, goal extracted: {len(with_goal)}")
    print(f"  domainSource=llm (site 10): {len(llm_domain)}")

    if not events:
        verdict = "INCONCLUSIVE"
        note = (
            "no context.understanding.extracted event was written, so the caller was "
            "not reached on these turns — a reachability finding, not a pass"
        )
    elif not attempted:
        verdict = "INCONCLUSIVE"
        note = (
            "the caller ran but the rule path answered every message, so the model "
            "tier was never consulted; the gate check should have caught this"
        )
    elif not ran:
        verdict = "FAIL"
        note = (
            f"{len(attempted)} turn(s) attempted the model and modelRan=false on every "
            "one — the call still is not completing in production"
        )
    else:
        verdict = "PASS"
        note = (
            f"{len(ran)}/{len(attempted)} attempted turns recorded modelRan=true, so "
            f"site 9 genuinely executes in production; {len(with_goal)} extracted a "
            f"goal. Site 10: {len(llm_domain)} turn(s) recorded domainSource=llm"
        )
        if not llm_domain:
            verdict = "PARTIAL"
            note += (
                " — but no turn reached the LLM domain tier, because rule confidence "
                "stayed above 0.55 on these messages. Site 10 remains unproven live"
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
