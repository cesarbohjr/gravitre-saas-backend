#!/usr/bin/env python3
"""P2 grounded synthesis paraphrases + follow-up. Isolated org. No invented GA/GSC."""
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
spec = importlib.util.spec_from_file_location("evc", ROOT / "scripts" / "audit-evidence-closure.py")
evc = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(evc)

OUT = ROOT / "docs" / "audits" / "gravitre-p2-synthesis-live.json"
SECTIONS = (
    "What is happening",
    "What appears important",
    "What I cannot conclude",
    "What is missing",
    "What to do next",
)


def _score(text: str) -> dict:
    body = text or ""
    return {
        "has_sections": all(s in body for s in SECTIONS),
        "canned_only_25": bool(
            "I found 25 deals" in body and "What is happening" not in body
        ),
        "invents_ga": bool(
            "sessions" in body.lower()
            and "google analytics" not in body.lower()
            and "not using" not in body.lower()
            and "pending" not in body.lower()
        ),
        "excerpt": body[:900],
    }


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
    prompts = [
        "How is my company doing?",
        "business performance snapshot",
        "Show my deals",
    ]
    out: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health_sha": health.get("git_sha"),
        "org_id": iso_org,
        "turns": [],
    }
    with httpx.Client(timeout=180) as client:
        for prompt in prompts:
            since = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
            cr = client.post(
                f"{evc.BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"p2-{uuid.uuid4().hex[:6]}"},
            )
            cr.raise_for_status()
            conv = str(cr.json()["id"])
            history: list = []
            turn = evc.chat_turn(client, headers, iso_org, conv, history, prompt)
            time.sleep(0.5)
            follow = None
            if prompt == "How is my company doing?":
                follow = evc.chat_turn(
                    client, headers, iso_org, conv, history, "What appears important?"
                )
            audits = evc.audit_since(sb, iso_org, since, 40)
            row = {
                "prompt": prompt,
                "conversation_id": conv,
                "first_ms": turn.get("first_useful_text_ms"),
                "score": _score(turn.get("assistant_excerpt") or ""),
                "follow_up": _score(follow.get("assistant_excerpt") or "") if follow else None,
                "invokes": [
                    a.get("action")
                    for a in audits
                    if a.get("action") in {"tool.invoke.completed", "tool.invoke.failed"}
                ][:6],
            }
            out["turns"].append(row)
    out["all_sections"] = all(t["score"]["has_sections"] for t in out["turns"])
    out["no_canned_only"] = all(not t["score"]["canned_only_25"] for t in out["turns"])
    OUT.write_text(json.dumps(out, indent=2, default=str)[:100000] + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, default=str)[:8000])
    return 0 if out["all_sections"] and out["no_canned_only"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
