"""Production verification helpers for assistant SSE and Part A/B checks."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
import importlib.util
import sys

_spec = importlib.util.spec_from_file_location(
    "smoke_ai_production", REPO / "scripts" / "smoke-ai-production.py"
)
smoke = importlib.util.module_from_spec(_spec)
sys.modules["smoke_ai_production"] = smoke
_spec.loader.exec_module(smoke)


def _setup_env() -> tuple[dict[str, str], str, str, str]:
    env = smoke._load_env()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET", "INTERNAL_API_SECRET"):
        if env.get(key):
            os.environ.setdefault(key, env[key])
    org_id, user_id, email = smoke._admin_org(env)
    token = smoke._mint_token(env, user_id, email)
    return env, org_id, user_id, token


def probe_assistant() -> None:
    _, org_id, _, token = _setup_env()
    stream = smoke._request_text(
        "POST",
        "/api/assistant/chat",
        token,
        org_id,
        {
            "messages": [{"role": "user", "content": "Say smoke-ok in one word."}],
            "org_id": org_id,
            "tools": ["agent_status"],
        },
        timeout=120,
    )
    events = smoke._parse_sse_json_events(stream)
    types = [event.get("type") for event in events]
    deltas = [event.get("delta", "") for event in events if event.get("type") == "text-delta"]
    print(json.dumps(
        {
            "event_types": types,
            "text_start": "text-start" in types,
            "text_delta_count": len(deltas),
            "text": "".join(deltas)[:300],
            "events_sample": events[:15],
        },
        indent=2,
    ))


def probe_company_question() -> None:
    _, org_id, _, token = _setup_env()
    stream = smoke._request_text(
        "POST",
        "/api/assistant/chat",
        token,
        org_id,
        {
            "messages": [
                {
                    "role": "user",
                    "content": "What do you know about our company that you have learned from past usage?",
                }
            ],
            "mode": "standard",
        },
        timeout=120,
    )
    events = smoke._parse_sse_json_events(stream)
    deltas = [event.get("delta", "") for event in events if event.get("type") == "text-delta"]
    print("".join(deltas)[:2000] or json.dumps(events[:10], indent=2))


def trigger_company_intelligence(org_id: str | None = None) -> None:
    env, default_org, _, _ = _setup_env()
    secret = env.get("INTERNAL_API_SECRET") or os.environ.get("INTERNAL_API_SECRET", "")
    if not secret:
        raise SystemExit("INTERNAL_API_SECRET missing")
    target_org = org_id or default_org
    body = json.dumps({"org_id": target_org}).encode()
    req = urllib.request.Request(
        f"{smoke.API_BASE}/api/internal/ops/company-intelligence-run",
        data=body,
        method="POST",
        headers={
            "X-Internal-Secret": secret,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            print(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        raise SystemExit(exc.code) from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["assistant", "company-chat", "trigger-intelligence"],
    )
    parser.add_argument("--org-id")
    args = parser.parse_args()
    if args.command == "assistant":
        probe_assistant()
    elif args.command == "company-chat":
        probe_company_question()
    else:
        trigger_company_intelligence(args.org_id)


if __name__ == "__main__":
    main()
