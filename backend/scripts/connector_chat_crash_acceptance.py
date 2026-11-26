"""Isolated real-DB connector_chat approval process-death acceptance.

Requires the exact disposable Supabase project/org already gated for MCP acceptance.
No customer provider is contacted. A local HTTP server independently records one
synthetic side effect, followed by immediate worker process death. A new process
replays the API request against the same persisted approval and must get HTTP 409.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.approval_action_binding import digest_plan_args

ARGS = {"qa": "connector-chat-death", "synthetic": True}
ACTION = "synthetic.record.create"
TOOL = "synthetic"
REVIEWER = "pr611-acceptance-reviewer"
ORG_NAME = "Gravitre MCP Acceptance QA"
EXPECTED_URL = "https://aadnwmjzrmbvadszroqt.supabase.co"


def client():
    from supabase import create_client
    return create_client(os.environ["MCP_ACCEPTANCE_URL"], os.environ["MCP_ACCEPTANCE_SERVICE_KEY"])


def check_env():
    if os.environ.get("MCP_CRASH_ACCEPTANCE") != "1":
        raise SystemExit("Refusing unapproved process-death acceptance")
    if os.environ.get("MCP_ACCEPTANCE_URL", "").rstrip("/") != EXPECTED_URL:
        raise SystemExit("Refusing non-acceptance Supabase database")
    if not os.environ.get("MCP_ACCEPTANCE_SERVICE_KEY") or not os.environ.get("MCP_ACCEPTANCE_ORG_ID"):
        raise SystemExit("Missing isolated QA acceptance configuration")


def api_decide(approval_id: str, port: int, crash: bool):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
    from app.config import Settings, get_settings
    from app.routers import workflows as wf
    from app.services import chat_connector_execution_service as connector_service
    from app.workflows import policy

    db = client()
    state = {
        "settings": Settings(
            app_env="dev", supabase_url=EXPECTED_URL, supabase_anon_key="a",
            supabase_service_role_key="s", supabase_jwt_secret="j",
        )
    }

    class FakeConnectorService:
        def plan_action(self, *_a, **_kw):
            return SimpleNamespace(
                tool_name=TOOL, invoke_action=ACTION, integration=TOOL,
                args=dict(ARGS), title="Synthetic QA provider write",
            )

        async def execute_plan(self, **_kwargs):
            if not crash:
                raise AssertionError("A restarted worker attempted a second provider dispatch")
            payload = json.dumps(ARGS).encode()
            req = Request(
                f"http://127.0.0.1:{port}/write", data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=10) as response:
                assert response.status == 200
            # The external provider completed the side effect, but no HTTP
            # result or approval-outcome update is possible after this point.
            os._exit(71)

    app.dependency_overrides[get_current_user] = lambda: {"user_id": REVIEWER}
    app.dependency_overrides[get_org_context] = lambda: os.environ["MCP_ACCEPTANCE_ORG_ID"]
    app.dependency_overrides[get_environment_context] = lambda: "production"
    app.dependency_overrides[get_settings] = lambda: state["settings"]
    with (
        patch.object(wf, "get_supabase_client", return_value=db),
        patch.object(wf, "get_plan_for_org", return_value={"features": {"approvals": True}}),
        patch.object(wf, "require_feature"),
        patch.object(wf, "has_capability", return_value=True),
        patch.object(wf, "write_audit_event"),
        patch.object(policy, "get_user_role", return_value="admin"),
        patch.object(connector_service, "get_chat_connector_execution_service", return_value=FakeConnectorService()),
    ):
        return TestClient(app).post(f"/api/approvals/{approval_id}/approve", json={})


def main():
    check_env()
    if len(sys.argv) == 4 and sys.argv[1] in {"child", "restart"}:
        response = api_decide(sys.argv[2], int(sys.argv[3]), crash=sys.argv[1] == "child")
        print(json.dumps({"status_code": response.status_code, "body": response.json()}))
        raise SystemExit(0)

    writes = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            writes.append(data)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    db = client()
    org_id = os.environ["MCP_ACCEPTANCE_ORG_ID"]
    org = db.table("organizations").select("name").eq("id", org_id).single().execute().data
    if (org or {}).get("name") != ORG_NAME:
        raise SystemExit("Refusing non-dedicated QA organization")
    approval_id = str(uuid.uuid4())
    context = {
        "conversation_id": f"qa-{approval_id}",
        "parameters": {"args": ARGS},
        "binding": {
            "tool_name": TOOL, "invoke_action": ACTION,
            "integration": TOOL, "args_digest": digest_plan_args(ARGS),
        },
        "qa": "PR611-connector-chat-process-crash",
    }
    try:
        db.table("approvals").insert({
            "id": approval_id, "org_id": org_id,
            "title": "QA611 synthetic connector_chat crash",
            "type": "connector_chat", "status": "pending",
            "context": context,
        }).execute()
        child = subprocess.run(
            [sys.executable, __file__, "child", approval_id, str(server.server_port)],
            env=os.environ.copy(), capture_output=True, text=True, timeout=65,
        )
        assert child.returncode == 71, (
            f"Worker did not terminate after fake provider write: "
            f"{child.returncode} {child.stderr[-1000:]} {child.stdout[-500:]}"
        )
        assert writes == [ARGS], f"Unexpected provider side effects: {writes}"
        row = db.table("approvals").select("status,reviewed_at,context").eq("id", approval_id).single().execute().data
        assert row["status"] == "approved" and row["reviewed_at"], "Approval claim not durably recorded"
        dispatch = row["context"].get("dispatch") or {}
        assert dispatch.get("state") == "claimed", f"Death boundary not persisted: {dispatch}"
        assert dispatch.get("args_digest") == digest_plan_args(ARGS)
        restart = subprocess.run(
            [sys.executable, __file__, "restart", approval_id, str(server.server_port)],
            env=os.environ.copy(), capture_output=True, text=True, timeout=65,
        )
        assert restart.returncode == 0, f"Restart process failed: {restart.stderr[-1000:]}"
        decision = json.loads(restart.stdout.strip().splitlines()[-1])
        assert decision["status_code"] == 409, decision
        assert writes == [ARGS], "Provider side effect was duplicated after restart"
        print(json.dumps({
            "result": "PASS", "worker_exit": 71, "provider_writes": len(writes),
            "durable_dispatch_state": dispatch["state"], "restart_http": 409,
            "independent_provider_side_effect_count": len(writes),
            "provider_outcome_verified": False,
        }))
    finally:
        try:
            db.table("approvals").delete().eq("id", approval_id).eq("org_id", org_id).execute()
            remaining = db.table("approvals").select("id").eq("id", approval_id).execute().data or []
            if remaining:
                raise RuntimeError("Synthetic approval cleanup failed")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
