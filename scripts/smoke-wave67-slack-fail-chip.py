#!/usr/bin/env python3
"""Supplemental Wave 6–7 claim-2 failure: Slack ReAct tool → real error_code chip shaping."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
import sys

sys.path.insert(0, str(BACKEND))

from isolated_conversation_org import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    mark_smoke_run,
    smoke_http_headers,
)

merged: dict[str, str] = {}
for p in (BACKEND / ".env", BACKEND / ".env.operator.local"):
    if p.is_file():
        merged.update({k: v for k, v in dotenv_values(p).items() if v})
for k, v in merged.items():
    os.environ.setdefault(k, v)

from app.config import get_settings  # noqa: E402
from app.operators.assistant_sse import format_react_tool_output  # noqa: E402
from app.operators.react_engine import ReActEngine  # noqa: E402
from app.services.tool_registry import get_tool_registry  # noqa: E402
from app.services.tool_types import ToolContext  # noqa: E402
from app.workflows.repository import get_supabase_client  # noqa: E402

ORG = DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID


async def main() -> None:
    settings = get_settings()
    client = get_supabase_client(settings)
    rows = client.table("organization_members").select("user_id").eq("org_id", ORG).limit(1).execute()
    actor = str((rows.data or [{}])[0].get("user_id") or "")
    reg = get_tool_registry()
    engine = ReActEngine(settings=settings, registry=reg)
    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=ORG,
        actor_id=actor,
        agent_id="synthetic-default",
        environment_name="production",
    )
    t0 = datetime.now(timezone.utc).isoformat()
    obs = await engine._execute_tool_call(
        ctx,
        "slack_post_message",
        {"channel": "#general", "text": "gravitre-wave67-spotcheck ignore"},
        allowed_tool_names={"slack_post_message"},
    )
    t1 = datetime.now(timezone.utc).isoformat()
    shaped = format_react_tool_output("slack_post_message", obs)
    out = {
        "at_start": t0,
        "at_end": t1,
        "observation": {
            "success": obs.get("success"),
            "error_code": obs.get("error_code"),
            "error": str(obs.get("error") or "")[:240],
            "action": obs.get("action"),
            "integration": obs.get("integration"),
        },
        "shaped_chip": shaped,
    }
    path = REPO / "docs" / "delivery" / "wave67-slack-fail-chip.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print("WROTE", path)


if __name__ == "__main__":
    asyncio.run(main())
