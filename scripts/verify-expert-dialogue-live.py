#!/usr/bin/env python3
"""Live before/after probe for expert dialogue substance (Prompt after structure).

Asks the same domain questions of Marketing, Sales, Finance agents and scores
practitioner vocabulary / framing (not length alone). Honesty: no fabricated metrics.
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
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "conv_beh_live",
    ROOT / "scripts" / "verify-conversational-behavior-live.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
parse_assistant = _mod.parse_assistant

_spec_all = importlib.util.spec_from_file_location(
    "conv_beh_all",
    ROOT / "scripts" / "verify-conversational-behavior-all-surfaces-live.py",
)
_all = importlib.util.module_from_spec(_spec_all)
assert _spec_all and _spec_all.loader
_spec_all.loader.exec_module(_all)
resolve_surface_agent = _all.resolve_surface_agent

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
LABEL = (os.environ.get("EXPERT_DIALOGUE_LABEL") or "before").strip()
OUT = ROOT / "docs" / "delivery" / f"expert-dialogue-{LABEL}-transcript.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()

# Representative domain questions. Wave 2 expands Legal/HR/Cyber substance
# (seeded into isolated smoke org when missing — same pattern as all-surfaces).
PROBES: list[dict[str, Any]] = [
    {
        "tag": "marketing",
        "needles": ["SEO Marketing Analyst", "Marketing Analyst", "SEO", "marketing"],
        "seed": None,
        "question": (
            "A deal stage update in HubSpot keeps failing — what should I check first "
            "as an SEO marketer tying pipeline to content?"
        ),
        "terms": [r"(?i)\b(pipeline-scoped|INVALID_PROPERTY|stage id|associations?|UTM)\b"],
    },
    {
        "tag": "sales",
        "needles": ["Sales Agent", "Sales Analyst", "Sales", "sales"],
        "seed": None,
        "question": (
            "How should we work a stalled opportunity that has a contact but no next "
            "step in the CRM?"
        ),
        "terms": [
            r"(?i)\b(champion|associat(e|ion)|close date|re-?qualif|mutual action|Opportunity)\b"
        ],
    },
    {
        "tag": "legal",
        "needles": ["Legal Agent", "Legal Analyst", "Legal", "Compliance", "legal"],
        "seed": {
            "name": "Legal Agent",
            "department": "legal",
            "role": "analyst",
            "purpose": "Legal and compliance guidance for contracts, privacy, and risk.",
        },
        "question": "Vendor NDA — what do I check first before we sign?",
        "terms": [
            r"(?i)\b(carveout|residual-?use|governing law|mutual|one-way|written release)\b"
        ],
    },
    {
        "tag": "hr",
        "needles": ["HR Agent", "People Agent", "HR Analyst", "HR", "hr"],
        "seed": {
            "name": "HR Agent",
            "department": "hr",
            "role": "analyst",
            "purpose": "HR and people-ops guidance for hiring, policy, and employee relations.",
        },
        "question": (
            "Should we score candidates with AI on scraped resumes from job boards?"
        ),
        "terms": [
            r"(?i)\b(scorecard|adverse impact|human review|ATS|first-party|applied through)\b"
        ],
    },
    {
        "tag": "cybersecurity",
        "needles": [
            "Cybersecurity Agent",
            "Security Agent",
            "Cyber Agent",
            "Cybersecurity",
            "security",
            "cyber",
        ],
        "seed": {
            "name": "Cybersecurity Agent",
            "department": "cybersecurity",
            "role": "analyst",
            "purpose": "Cybersecurity guidance for access control, hardening, and incident response.",
        },
        "question": "What's the first hardening move for SaaS admin accounts?",
        "terms": [
            r"(?i)\b(MFA|phishing-resistant|passkey|security key|just-in-time|JIT|SSO)\b"
        ],
    },
]

FABRICATED_METRIC = re.compile(
    r"(?i)\b(\d{2,}%\s+(lift|increase|improvement)|exactly\s+\d+\s+deals|"
    r"we generated\s+\$\d+|your open rate is\s+\d+)\b"
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if merged.get(k):
            os.environ[k] = merged[k]
    return merged


def score_reply(text: str, term_patterns: list[str]) -> dict[str, Any]:
    hits = [p for p in term_patterns if re.search(p, text or "")]
    fabricated = bool(FABRICATED_METRIC.search(text or ""))
    # Practitioner framing: concrete check / next action, not pure essay
    actiony = bool(
        re.search(
            r"(?i)\b(check|verify|look( at| up)|confirm|first|before|don't|do not|"
            r"won't|approval|stage|property|refund|associat)\b",
            text or "",
        )
    )
    words = len((text or "").split())
    # After ship: require distinctive expert marker (not just generic CRM words).
    return {
        "term_hits": len(hits),
        "term_patterns_matched": len(hits),
        "practitioner_framing": actiony,
        "fabricated_metric": fabricated,
        "word_count": words,
        "pass": len(hits) >= 1 and actiony and not fabricated and 20 <= words <= 220,
    }


async def main() -> int:
    env = load_env()
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

    async with httpx.AsyncClient() as client:
        h = await client.get(f"{BASE}/health", timeout=30.0)
        h.raise_for_status()
        tip = str(h.json().get("git_sha") or "")
        if EXPECT_SHA and not tip.lower().startswith(EXPECT_SHA.lower()):
            OUT.write_text(
                json.dumps({"verdict": "FAIL", "fatal": f"tip {tip} != {EXPECT_SHA}"}, indent=2),
                encoding="utf-8",
            )
            return 1

        results = []
        for probe in PROBES:
            tag = str(probe["tag"])
            question = str(probe["question"])
            terms = list(probe["terms"])
            agent = resolve_surface_agent(
                sb,
                org_id,
                user_id,
                needles=list(probe.get("needles") or []),
                seed=probe.get("seed"),
            )
            if not agent:
                results.append({"tag": tag, "ok": False, "error": "agent_not_found"})
                continue
            cr = await client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"expert-dlg-{LABEL}-{tag}-{uuid.uuid4().hex[:6]}"},
                timeout=60.0,
            )
            cr.raise_for_status()
            conv_id = str(cr.json()["id"])
            async with client.stream(
                "POST",
                f"{BASE}/api/assistant/chat",
                headers=headers,
                json={
                    "messages": [{"role": "user", "parts": [{"type": "text", "text": question}]}],
                    "org_id": org_id,
                    "mode": "standard",
                    "conversation_id": conv_id,
                    "agent_id": str(agent["id"]),
                },
                timeout=180.0,
            ) as r:
                chunks: list[bytes] = []
                async for part in r.aiter_bytes():
                    chunks.append(part)
                status = r.status_code
            assistant = parse_assistant(b"".join(chunks).decode("utf-8", errors="replace"))
            sc = score_reply(assistant, terms)
            results.append(
                {
                    "tag": tag,
                    "agent": agent.get("name"),
                    "agent_id": agent.get("id"),
                    "conversation_id": conv_id,
                    "question": question,
                    "assistant": assistant,
                    "http_status": status,
                    "score": sc,
                    "ok": sc["pass"] and status == 200,
                    "seeded": bool(probe.get("seed"))
                    and agent.get("name") == (probe.get("seed") or {}).get("name"),
                }
            )
            await asyncio.sleep(1.0)

    passed = sum(1 for r in results if r.get("ok"))
    # Before label: we still write scores for comparison; after requires all pass
    verdict = "PASS" if passed == len(results) and results else "PARTIAL" if results else "FAIL"
    if LABEL == "before":
        verdict = "BASELINE"
    artifact = {
        "feature": "expert_dialogue_library",
        "label": LABEL,
        "checkedAt": utcnow(),
        "git_sha": tip,
        "org_id": org_id,
        "verdict": verdict,
        "passed": passed,
        "total": len(results),
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": verdict,
                "git_sha": tip,
                "passed": passed,
                "total": len(results),
                "scores": {r.get("tag"): r.get("score") for r in results},
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if LABEL == "before" or verdict == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception:
        import traceback

        traceback.print_exc()
        raise SystemExit(2) from None
