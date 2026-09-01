"""Phase B — is there ANY turn shape that reaches the grounding validator?

Three attempts have now produced zero `answer.grounding.validated` events with the
audit code confirmed live (tip `9080bc87`), so the question is no longer "did the
signature fix work" but "is this code path reachable at all".

`execute_task_streaming` has many early returns before the finalize call, and
several of them pass `validation=None` outright — the ReAct write-approval gate
and the connector-fallback branch among them. This sweeps distinct query shapes
chosen to avoid those branches and reports, per shape, whether the validator
fired.

Not a pass/fail gate. The output is a reachability map.
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
OUT = ROOT / "docs" / "delivery" / "grounding-validator-reachability.json"

# Each shape targets a different branch of execute_task_streaming. The aim is a
# turn that reaches RAG answering without a tool call, an approval gate, or the
# conversational fast path.
SHAPES: list[tuple[str, str, str]] = [
    (
        "factual_knowledge_standard",
        "standard",
        "Summarize what our documentation says about data retention obligations.",
    ),
    (
        "reasoning_mode_analysis",
        "reasoning",
        "Based on our internal material, analyze the tradeoffs between annual and "
        "monthly billing for a mid-market customer, and cite what you relied on.",
    ),
    (
        "grounding_pressure_unanswerable",
        "standard",
        "According to our own internal policy documents, what is the exact number "
        "of business days we guarantee for a security questionnaire turnaround?",
    ),
    (
        "multi_hop_business_question",
        "reasoning",
        "What does our knowledge base say about SOC 2 evidence collection, and how "
        "does that affect what we can promise a prospect this quarter?",
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
    validation: Any = None
    explanation = ""
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
        if isinstance(data, dict):
            if data.get("validation") is not None:
                validation = data.get("validation")
            if data.get("answerExplanation") or data.get("answer_explanation"):
                explanation = str(
                    data.get("answerExplanation") or data.get("answer_explanation")
                )
    return {
        "assistant": "".join(texts).strip(),
        "validation": validation,
        "answer_explanation": explanation,
    }


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
    base_headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }

    git_sha = str(httpx.get(f"{BASE}/health", timeout=30).json().get("git_sha") or "")
    started_at = datetime.now(timezone.utc)
    print(f"deployed tip: {git_sha}\norg: {org_id}\n")

    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient() as client:
        for label, mode, query in SHAPES:
            r = await client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in base_headers.items() if k != "Accept"},
                json={"title": f"reach-{label}-{uuid.uuid4().hex[:6]}"},
                timeout=60,
            )
            r.raise_for_status()
            conv = str(r.json()["id"])

            body = {
                "messages": [{"role": "user", "parts": [{"type": "text", "text": query}]}],
                "org_id": org_id,
                "mode": mode,
                "conversation_id": conv,
            }
            t0 = time.perf_counter()
            chunks: list[bytes] = []
            async with client.stream(
                "POST",
                f"{BASE}/api/assistant/chat",
                json=body,
                headers=base_headers,
                timeout=300.0,
            ) as resp:
                async for c in resp.aiter_bytes():
                    chunks.append(c)
            parsed = parse_sse(b"".join(chunks).decode("utf-8", "replace"))
            elapsed = int((time.perf_counter() - t0) * 1000)

            print(f"[{label}] mode={mode} {elapsed}ms")
            print(f"    explanation: {parsed['answer_explanation'][:90]}")
            print(f"    validation : {json.dumps(parsed['validation'])[:150]}")
            print(f"    reply      : {parsed['assistant'][:130]}")
            results.append(
                {
                    "label": label,
                    "mode": mode,
                    "query": query,
                    "conversation_id": conv,
                    "elapsed_ms": elapsed,
                    "answer_explanation": parsed["answer_explanation"],
                    "validation_in_sse": parsed["validation"],
                    "assistant": parsed["assistant"][:600],
                }
            )
            print()

    print("waiting 15s for audit writes...")
    await asyncio.sleep(15)

    since = (started_at - timedelta(minutes=2)).isoformat()
    audits = (
        sb.table("audit_events")
        .select("created_at,action,resource_id,metadata")
        .eq("action", "answer.grounding.validated")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
        .data
        or []
    )
    print(f"answer.grounding.validated events since probe start: {len(audits)}")
    for a in audits:
        m = a.get("metadata") or {}
        print(
            f"  {a['created_at']} mode={m.get('modeKey')} "
            f"confSource={m.get('confidenceSource')} assessorRan={m.get('assessorRan')} "
            f"isValid={m.get('isValid')} ragSources={m.get('ragSourceCount')} "
            f"ms={m.get('durationMs')}"
        )

    shapes_with_sse_validation = [r["label"] for r in results if r["validation_in_sse"]]
    result = {
        "deployed_git_sha": git_sha,
        "captured_at": started_at.isoformat(),
        "org_id": org_id,
        "shapes": results,
        "grounding_audit_count": len(audits),
        "grounding_audits": audits,
        "shapes_reporting_validation_in_sse": shapes_with_sse_validation,
        "finding": (
            "REACHED — at least one turn shape executed the grounding validator"
            if audits
            else "UNREACHED — no turn shape tried has executed the grounding validator"
        ),
    }
    OUT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nFINDING: {result['finding']}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
