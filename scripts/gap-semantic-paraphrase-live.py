#!/usr/bin/env python3
"""Semantic-class paraphrases for CEO/ops — not golden-phrase only."""
from __future__ import annotations

import importlib.util
import json
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))

spec = importlib.util.spec_from_file_location(
    "evc", ROOT / "scripts" / "audit-evidence-closure.py"
)
evc = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(evc)

OUT = ROOT / "docs" / "audits" / "gravitre-semantic-paraphrase-live.json"

PROMPTS = [
    "How is my company doing?",
    "How's the company doing?",
    "Give me a business performance snapshot from connected systems.",
]


def main() -> int:
    env = evc.load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    health = httpx.get(f"{evc.BASE}/health", timeout=45).json()
    iso_org, user_id, email = evc.resolve_isolated_conversation_actor(env, sb)
    token = evc.mint(env, user_id, email)
    headers = {
        **evc.smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "X-Org-Id": iso_org,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    turns = []
    with httpx.Client(timeout=180) as client:
        for prompt in PROMPTS:
            cr = client.post(
                f"{evc.BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"para-{uuid.uuid4().hex[:6]}"},
            )
            cr.raise_for_status()
            conv = str(cr.json()["id"])
            since = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
            history: list = []
            turn = evc.chat_turn(client, headers, iso_org, conv, history, prompt)
            time.sleep(1.0)
            audits = evc.audit_since(sb, iso_org, since, 80)
            turns.append(
                {
                    "prompt": prompt,
                    "conversation_id": conv,
                    "http": turn.get("http_status"),
                    "first_ms": turn.get("first_useful_text_ms"),
                    "excerpt": (turn.get("assistant_excerpt") or "")[:500],
                    "actions": [a.get("action") for a in audits[:24]],
                    "invokes": [
                        a
                        for a in audits
                        if a.get("action") == "tool.invoke.completed"
                    ][:4],
                }
            )
    OUT.write_text(
        json.dumps(
            {"health": health.get("git_sha"), "turns": turns},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"health": health.get("git_sha"), "n": len(turns)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
