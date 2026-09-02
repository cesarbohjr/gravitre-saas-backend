"""Live proof: is the re-enabled clarification polish (site 11) running in production?

Site 11 is the one site in the twelve that needs no audit instrument, which
matters after three separate "one layer too low" instrument-placement misses.
`_polish_question`'s output IS the user-visible reply, so the reply text itself
is the evidence:

    dormant -> `_polish_question` returns None, `generate_clarification_question`
               falls back to `polished or question`, and the user receives the
               raw template VERBATIM.
    fixed   -> the model rewrites the template into one natural question.

So the templates are the discriminator. Their literal strings are lifted from
ClarificationEngine.CLARIFICATION_TRIGGERS, and a reply containing one verbatim
is proof the model did not run.

Two states must not be confused, which is what made earlier sites inconclusive:

    clarification never triggered  -> nothing to polish; INCONCLUSIVE, not a pass
    triggered and verbatim        -> FAIL, still dormant
    triggered and rewritten       -> PASS

`dialogue_mode=clarify` in the SSE metadata separates the first case from the
others, so a turn that simply got answered cannot be scored either way.

`connector_unavailable` is deliberately not probed: agent_intelligence.py:2866
overrides the question with `shaped["error"]` on that branch, so the polish is
discarded and the branch would report a false FAIL.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import uuid
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
OUT = ROOT / "docs" / "delivery" / "clarification-polish-live.json"

# Verbatim fragments from CLARIFICATION_TRIGGERS. Any of these appearing in a
# reply means the template reached the user unrewritten.
TEMPLATE_MARKERS = [
    "Could you share the target and any constraints?",  # under_specified_action
    "Could you share that?",                            # missing_required_param
    "did you mean —",                                   # ambiguous_entity
    "Would you like to connect it first?",              # connector_unavailable
]

# Deliberately under-specified action requests: an action verb with no target,
# which is what drives should_clarify to under_specified_action or
# missing_required_param rather than a normal answer.
SCENARIOS = [
    {
        "label": "update_no_target",
        "message": "Can you update it for me?",
    },
    {
        "label": "send_no_recipient",
        "message": "Please send that over.",
    },
    {
        "label": "archive_no_scope",
        "message": "Go ahead and archive those.",
    },
    {
        "label": "vague_action_request",
        "message": "I need you to handle the thing for the client.",
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


def parse_sse(raw: str) -> tuple[str, bool]:
    """Returns (assistant_text, saw_clarify_dialogue_mode)."""
    texts: list[str] = []
    clarify = False
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
        for key in ("dialogue_mode", "dialogueMode"):
            if str(obj.get(key) or "") == "clarify":
                clarify = True
        data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
        for key in ("dialogue_mode", "dialogueMode"):
            if str(data.get(key) or "") == "clarify":
                clarify = True
    return "".join(texts).strip(), clarify


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

    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        for sc in SCENARIOS:
            print(f"[{sc['label']}] {sc['message']!r}")
            r = await client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"clarify-{sc['label']}-{uuid.uuid4().hex[:6]}"},
                timeout=60,
            )
            r.raise_for_status()
            conv = str(r.json()["id"])

            body = {
                "messages": [
                    {"role": "user", "parts": [{"type": "text", "text": sc["message"]}]}
                ],
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
                print(f"    stream error: {exc}")
            reply, clarify_mode = parse_sse(b"".join(chunks).decode("utf-8", "replace"))

            verbatim = [m for m in TEMPLATE_MARKERS if m.lower() in reply.lower()]
            if not clarify_mode:
                verdict = "INCONCLUSIVE — clarification did not trigger"
            elif verbatim:
                verdict = "FAIL — raw template reached the user"
            else:
                verdict = "PASS — clarification triggered and was rewritten"

            print(f"  dialogue_mode=clarify : {clarify_mode}")
            print(f"  verbatim template hit : {verbatim or 'none'}")
            print(f"  reply: {reply[:170]!r}")
            print(f"  {verdict}\n")

            results.append(
                {
                    "label": sc["label"],
                    "conversation_id": conv,
                    "message": sc["message"],
                    "assistant": reply[:600],
                    "clarify_dialogue_mode": clarify_mode,
                    "verbatim_template_markers": verbatim,
                    "verdict": verdict,
                }
            )
            await asyncio.sleep(3)

    triggered = [r for r in results if r["clarify_dialogue_mode"]]
    passed = [r for r in triggered if not r["verbatim_template_markers"]]
    failed = [r for r in triggered if r["verbatim_template_markers"]]

    print("=== RESULT ===")
    print(f"scenarios run                  : {len(results)}")
    print(f"clarification actually triggered: {len(triggered)}")
    print(f"  rewritten (polish ran)       : {len(passed)}")
    print(f"  verbatim template (dormant)  : {len(failed)}")

    if not triggered:
        verdict = (
            "INCONCLUSIVE — clarification never triggered on any scenario, so the "
            "polish path was not exercised. This is a reachability result, not a "
            "pass, and must not be reported as one."
        )
    elif failed:
        verdict = (
            f"FAIL — {len(failed)} of {len(triggered)} triggered clarifications "
            "delivered the raw template verbatim; the polish call is still not running"
        )
    else:
        verdict = (
            f"PASS — {len(passed)} of {len(triggered)} triggered clarifications were "
            "rewritten rather than delivered as the verbatim template, so "
            "_polish_question genuinely reaches the model in production"
        )
    print(f"\n{verdict}")

    OUT.write_text(
        json.dumps(
            {
                "git_sha": git_sha,
                "org_id": org_id,
                "template_markers": TEMPLATE_MARKERS,
                "scenarios": results,
                "triggered": len(triggered),
                "rewritten": len(passed),
                "verbatim": len(failed),
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
