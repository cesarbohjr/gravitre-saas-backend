"""Live proof: does the re-enabled pending-plan intent classifier (site 6) work in production?

The local before/after already proves the router is entered now and was not
before. What it cannot show is the half needing real AI credentials: whether the
model actually labels these replies, instead of the two fallbacks the dormant
path always produced.

This site has exactly one production caller — `agent_intelligence.py`, orphan
strategic-plan recovery — gated on a `current_plan` with a goal and NO
`pending_task`. So the scenario has to construct that exact state; a normal
approval hold goes to site 5's classifier instead and would prove nothing here.

Two discriminators, both externally visible:

  1. GENERAL PATH (no modify hint). Dormant → "unclear" → the caller emits a
     verbatim prompt: "I still have a pending plan (...). Reply `abandon` to
     drop it ... or `hold` ...". That string is emitted on no other branch, so
     its presence means the model did not classify and its absence means it did.
     This is the deterministic one.

  2. MODIFY-HINT PATH. Dormant → "modify" → the caller appends
     " (regarding plan: {goal})" to the user's message before answering. The
     goal here contains a nonsense token that exists nowhere else, so if it
     appears in the reply, the abandoned goal was carried into the turn that
     rejected it.

Both replies unambiguously mean stop, so a correct classifier returns "cancel"
for each.
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
OUT = ROOT / "docs" / "delivery" / "pending-plan-intent-live.json"

# A nonsense token that cannot occur naturally, so any appearance in the reply
# is proof the abandoned goal was injected rather than coincidence.
CANARY = "Zenphara"
GOAL = f"Create a HubSpot list called {CANARY} Renewals and add the matched deals"

SCENARIOS = [
    (
        "general_path_cancel",
        "hold off, I need to run this past our finance lead before anything happens",
        False,  # must NOT hit re_modify_hint
    ),
    (
        "modify_hint_cancel",
        "don't bother with that, we're going a completely different direction now",
        True,  # must hit re_modify_hint
    ),
]

# Emitted only by the `unclear` branch of the orphan-plan caller.
UNCLEAR_MARKERS = (
    "reply `abandon` to drop it",
    "reply abandon to drop it",
    "i still have a pending plan",
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


def task_state_of(sb: Any, conv_id: str) -> dict[str, Any]:
    rows = (
        sb.table("conversations").select("task_state").eq("id", conv_id).limit(1).execute().data
        or []
    )
    return (rows[0].get("task_state") or {}) if rows else {}


def seed_orphan_plan(sb: Any, conv_id: str) -> dict[str, Any]:
    """Write the exact state the production caller requires: a plan, no pending task."""
    state = {
        "current_plan": {
            "goal": GOAL,
            "steps": [
                {"action": "hubspot.lists.create", "label": "Create list"},
                {"action": "hubspot.lists.add_members", "label": "Add members"},
            ],
        },
        "pending_task": None,
        "pending_steps": [],
        "completed_steps": [],
    }
    sb.table("conversations").update({"task_state": state}).eq("id", conv_id).execute()
    return state


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
    print(f"deployed tip: {git_sha}\norg: {org_id}\ncanary token: {CANARY}\n")

    # Sanity-check the branch each message is supposed to take, so a failure to
    # discriminate cannot be blamed on picking the wrong phrasing.
    from app.services.conversation_turn_controller import re_modify_hint

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
        for label, message, expect_hint in SCENARIOS:
            print(f"[{label}]")
            actual_hint = re_modify_hint(message)
            if actual_hint != expect_hint:
                print(f"  phrasing takes the wrong branch (hint={actual_hint}) — skipping")
                results.append(
                    {"label": label, "ran": False, "note": "phrasing took the wrong branch"}
                )
                continue

            r = await client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"ppi-{label}-{uuid.uuid4().hex[:6]}"},
                timeout=60,
            )
            r.raise_for_status()
            conv = str(r.json()["id"])

            seeded = seed_orphan_plan(sb, conv)
            before = task_state_of(sb, conv)
            plan_present = bool((before.get("current_plan") or {}).get("goal"))
            no_pending = not before.get("pending_task")
            print(f"  seeded orphan plan: plan={plan_present} no_pending={no_pending}")

            if not (plan_present and no_pending):
                results.append(
                    {"label": label, "ran": False, "note": "could not seed the orphan-plan state"}
                )
                print("  SKIP — state not seeded\n")
                continue

            reply = await turn(client, conv, message)
            await asyncio.sleep(3)
            after = task_state_of(sb, conv)

            low = reply.lower()
            hit_unclear = any(m in low for m in UNCLEAR_MARKERS)
            canary_leaked = CANARY.lower() in low
            plan_cleared = not (after.get("current_plan") or {}).get("goal")

            print(f"  reply: {reply[:200]!r}")
            print(f"  'abandon or hold' prompt (unclear fallback): {hit_unclear}")
            print(f"  canary '{CANARY}' leaked into reply (modify injection): {canary_leaked}")
            print(f"  current_plan cleared: {plan_cleared}\n")

            results.append(
                {
                    "label": label,
                    "ran": True,
                    "conversation_id": conv,
                    "message": message,
                    "hits_modify_hint": actual_hint,
                    "seeded_goal": seeded["current_plan"]["goal"],
                    "assistant": reply[:800],
                    "unclear_fallback_prompt": hit_unclear,
                    "canary_leaked": canary_leaked,
                    "current_plan_cleared": plan_cleared,
                }
            )

    ran = [r for r in results if r.get("ran")]
    general = next((r for r in ran if r["label"] == "general_path_cancel"), None)
    hinted = next((r for r in ran if r["label"] == "modify_hint_cancel"), None)

    print("=== RESULT ===")
    print(f"scenarios run: {len(ran)}/{len(SCENARIOS)}")

    if not ran:
        verdict = "INCONCLUSIVE"
        note = "the orphan-plan state could not be exercised, so nothing was tested"
    elif general is None:
        verdict = "PARTIAL"
        note = "the deterministic general-path scenario did not run"
    elif general["unclear_fallback_prompt"]:
        verdict = "FAIL"
        note = (
            "the general-path reply still produced the 'abandon or hold' prompt, which "
            "is the dormant 'unclear' fallback verbatim — the model did not classify it"
        )
    else:
        leaked = bool(hinted and hinted["canary_leaked"])
        verdict = "PASS"
        note = (
            "the general-path reply was classified without falling back to the "
            "'abandon or hold' prompt, so the model call is genuinely running in "
            "production"
        )
        if leaked:
            verdict = "PARTIAL"
            note = (
                "the general path classified correctly, but the modify-hint reply "
                f"still leaked the canary '{CANARY}' into the answer — the stale goal "
                "is being carried into the turn that rejected it"
            )

    print(f"\n{verdict} — {note}")

    OUT.write_text(
        json.dumps(
            {
                "deployed_git_sha": git_sha,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "org_id": org_id,
                "site": "backend/app/services/conversation_turn_controller.py:273",
                "canary": CANARY,
                "verdict": verdict,
                "note": note,
                "scenarios": results,
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
