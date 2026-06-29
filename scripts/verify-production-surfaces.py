"""Live production verification for Part B chat surfaces."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "smoke_ai_production", REPO / "scripts" / "smoke-ai-production.py"
)
smoke = importlib.util.module_from_spec(_spec)
sys.modules["smoke_ai_production"] = smoke
_spec.loader.exec_module(smoke)


def setup() -> tuple[str, str, str]:
    env = smoke._load_env()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if env.get(key):
            os.environ.setdefault(key, env[key])
    org_id, user_id, email = smoke._admin_org(env)
    token = smoke._mint_token(env, user_id, email)
    return org_id, user_id, token


def sse_text(path: str, token: str, org_id: str, body: dict) -> tuple[list[str], str]:
    stream = smoke._request_text("POST", path, token, org_id, body, timeout=120)
    events = smoke._parse_sse_json_events(stream)
    types = [str(event.get("type")) for event in events]
    deltas = [str(event.get("delta", "")) for event in events if event.get("type") == "text-delta"]
    return types, "".join(deltas)


def json_get(path: str, token: str, org_id: str) -> dict:
    return smoke._request("GET", path, token, org_id)


def main() -> None:
    org_id, _, token = setup()
    results: dict[str, object] = {}

    # B1 Agent chat UI
    agents = json_get("/api/agents", token, org_id).get("agents") or []
    agent_id = str((agents[0] or {}).get("id") or "")
    types, text = sse_text(
        "/api/assistant/chat",
        token,
        org_id,
        {
            "messages": [{"role": "user", "content": "Summarize our connected integrations in one sentence."}],
            "agentId": agent_id,
            "tools": ["knowledge_base", "agent_status", "connector_status", "workflow_runs", "search_web"],
        },
    )
    results["agent_chat_ui"] = {
        "pass": "text-start" in types and "text-delta" in types and bool(text.strip()),
        "types": types,
        "text_excerpt": text[:400],
    }

    # B3 Conversation persistence
    _, turn1 = sse_text(
        "/api/assistant/chat",
        token,
        org_id,
        {"messages": [{"role": "user", "content": "My favorite color is blue. Remember that."}]},
    )
    conv_id = None
    # conversation id may be returned in finish metadata — probe via conversations API after send
    convs = json_get("/api/conversations?limit=1", token, org_id)
    rows = convs.get("conversations") or convs.get("items") or []
    if rows:
        conv_id = str(rows[0].get("id") or "")
    types2, turn2 = sse_text(
        "/api/assistant/chat",
        token,
        org_id,
        {
            **({"conversation_id": conv_id} if conv_id else {}),
            "messages": [{"role": "user", "content": "What is my favorite color?"}],
        },
    )
    results["conversation_persistence"] = {
        "pass": "blue" in turn2.lower(),
        "conversation_id": conv_id,
        "turn2_excerpt": turn2[:400],
        "turn2_types": types2,
    }

    # B4 Daily briefing
    briefing = json_get("/api/assistant/daily-briefing", token, org_id)
    body = json.dumps(briefing)
    results["daily_briefing"] = {
        "pass": len(body) > 80 and briefing.get("briefing") is not None,
        "keys": list(briefing.keys()),
        "excerpt": body[:500],
    }

    # B5 Admin bodies
    outcomes = json_get("/api/admin/intelligence/outcomes", token, org_id)
    suggestions = json_get("/api/admin/optimization-suggestions", token, org_id)
    results["admin_outcomes"] = {
        "pass": isinstance(outcomes, dict) and ("items" in outcomes or "outcomes" in outcomes or "summary" in outcomes),
        "keys": list(outcomes.keys()),
        "excerpt": json.dumps(outcomes)[:400],
    }
    results["admin_optimization_suggestions"] = {
        "pass": isinstance(suggestions, dict),
        "keys": list(suggestions.keys()),
        "excerpt": json.dumps(suggestions)[:400],
    }

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
