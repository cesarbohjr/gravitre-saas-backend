#!/usr/bin/env python3
"""STA-303 live: never-connected connector → errorCode=connector_not_connected.

Proves the tool/chip path against prod org data (Asana has no connector row).
Chat SSE is best-effort; invoke is the acceptance bar when ReAct skips the vendor tool.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
    if path.is_file():
        try:
            for k, v in dotenv_values(path).items():
                if v:
                    os.environ.setdefault(k, v)
        except UnicodeDecodeError:
            pass

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"


async def _invoke_never_connected() -> dict:
    import httpx

    from app.config import get_settings
    from app.operators.assistant_sse import format_react_tool_output
    from app.operators.react_engine import ReActEngine
    from app.services.tool_registry import get_tool_registry
    from app.services.tool_types import ToolContext
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    rows = (
        client.table("organization_members")
        .select("user_id")
        .eq("org_id", ORG)
        .limit(1)
        .execute()
    )
    actor = str((rows.data or [{}])[0].get("user_id") or "")
    health = httpx.get("https://api.gravitre.app/health", timeout=30).json()
    conn = httpx.get(
        "https://api.gravitre.app/api/connectors",
        headers={
            "Authorization": f"Bearer {_mint()}",
            "X-Org-Id": ORG,
            "X-Environment": "production",
        },
        timeout=60,
    ).json()
    vendors = sorted({str(c.get("vendor") or "").lower() for c in (conn.get("connectors") or [])})
    probe = "asana" if "asana" not in vendors else "monday"
    tool = f"{probe}_workspaces_list"
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
    obs = await engine._execute_tool_call(ctx, tool, {}, allowed_tool_names={tool})
    shaped = format_react_tool_output(tool, obs)
    code = obs.get("error_code") or shaped.get("errorCode")
    return {
        "kind": "sta303-never-connected-live",
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "prod_git_sha": health.get("git_sha"),
        "org_id": ORG,
        "probe_vendor": probe,
        "vendors_present": vendors,
        "vendor_present": probe in vendors,
        "path": "react_tool_invoke",
        "tool": tool,
        "observation": {
            "success": obs.get("success"),
            "error_code": obs.get("error_code"),
            "error": str(obs.get("error") or "")[:300],
        },
        "shaped_chip": shaped,
        "pass": code == "connector_not_connected",
        "note": (
            "PASS = never-connected vendor tool returns error_code/errorCode "
            "connector_not_connected (not validation_error). Smoke-org Slack is "
            "auth_expired — use a vendor with no connector row (Asana)."
        ),
    }


def _mint() -> str:
    import time

    import jwt

    url = os.environ["SUPABASE_URL"].rstrip("/")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "f7e32f06-49df-4e73-8962-f41c21850762",
            "email": "cesar@gravitre.app",
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        os.environ["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def main() -> int:
    report = asyncio.run(_invoke_never_connected())
    out = REPO / "docs" / "delivery" / "sta303-never-connected-live.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("WROTE", out)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
