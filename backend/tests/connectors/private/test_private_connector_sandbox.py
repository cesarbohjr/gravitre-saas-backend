"""Private connector sandbox runner tests (STA-98)."""
from __future__ import annotations

import json
import subprocess
import sys

from app.config import Settings
from app.connectors.private.runtime import run_private_handler
from app.services.tool_types import ToolContext


def test_sandbox_runner_executes_handler():
    source = """
def tickets_list(ctx, params):
    return {"success": True, "action": "acme_tools.tickets.list", "data": {"tickets": []}}
"""
    payload = {
        "handlerSource": source,
        "functionName": "tickets_list",
        "action": "acme_tools.tickets.list",
        "params": {},
        "context": {"orgId": "org-1"},
    }
    proc = subprocess.run(
        [sys.executable, "-m", "app.connectors.private.sandbox_runner"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    envelope = json.loads(proc.stdout)
    assert envelope["ok"] is True
    assert envelope["result"]["data"]["tickets"] == []


def test_run_private_handler_via_runtime():
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        supabase_jwt_secret="secret",
    )
    ctx = ToolContext(
        settings=settings,
        client=None,
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-1",
    )
    source = """
def tickets_list(ctx, params):
    return {"success": True, "action": "acme_tools.tickets.list", "data": {"count": 1}}
"""
    result = run_private_handler(
        settings,
        handler_source=source,
        action="acme_tools.tickets.list",
        ctx=ctx,
        params={},
    )
    assert result.success is True
    assert result.data["count"] == 1
