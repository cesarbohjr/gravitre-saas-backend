"""Opt-in process-death acceptance for MCP approval consumption.

Run ONLY against the isolated acceptance Supabase project with a disposable org:
  MCP_CRASH_ACCEPTANCE=1 MCP_ACCEPTANCE_URL=... MCP_ACCEPTANCE_SERVICE_KEY=... \\
  MCP_ACCEPTANCE_ORG_ID=... python backend/scripts/mcp_approval_crash_acceptance.py

The child runs the real MCPClientService.execute_tool approval/dispatch path.
A local synthetic HTTP provider records the side effect before the child is
terminated via os._exit(71). A separate new process retries the same approval.
No external provider or customer action is invoked. The test is opt-in.
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
from unittest.mock import AsyncMock, patch
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.mcp_client_service import MCPClientService, mcp_approval_target_digest, mcp_input_sha256

ARGS = {"qa": "crash-restart", "synthetic": True}
TOOL = {"id": "synthetic-mcp-write", "server_id": "synthetic-server", "tool_name": "create_record", "capability_tier": "write", "enabled": True}
SERVER = {"id": "synthetic-server", "server_url": "http://127.0.0.1/synthetic", "transport": "streamable_http", "enabled": True, "auth_config": {}}


def client():
    from supabase import create_client
    return create_client(os.environ["MCP_ACCEPTANCE_URL"], os.environ["MCP_ACCEPTANCE_SERVICE_KEY"])


async def dispatch(approval_id: str, port: int, *, crash: bool):
    svc = MCPClientService(settings=SimpleNamespace(connector_secrets_encryption_key="k" * 32))
    db = client()

    async def synthetic_provider(_server, _name, args):
        payload = json.dumps(args).encode()
        def post():
            req = Request(f"http://127.0.0.1:{port}/write", data=payload, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=10) as response:
                assert response.status == 200
        await asyncio.to_thread(post)
        if crash:
            # Provider side effect has been durably recorded by the parent process.
            os._exit(71)
        return {"accepted": True}

    with (
        patch.object(svc, "_client", return_value=db),
        patch.object(svc, "_load_tool", new=AsyncMock(return_value=TOOL)),
        patch.object(svc, "_load_server", new=AsyncMock(return_value=SERVER)),
        patch.object(svc, "_preflight_server", new=AsyncMock()),
        patch.object(svc, "_call_mcp_server", new=synthetic_provider),
        patch.object(svc, "_log_execution", new=AsyncMock()),
        patch.object(svc, "_audit_execution", new=AsyncMock()),
        patch("app.services.mcp_client_service.enforce_mcp_rate_limit"),
    ):
        try:
            return await svc.execute_tool(TOOL["id"], os.environ["MCP_ACCEPTANCE_ORG_ID"], ARGS, approval_id=approval_id)
        except ValueError as exc:
            return {"status": "rejected", "error": str(exc)}


def main():
    if os.environ.get("MCP_CRASH_ACCEPTANCE") != "1":
        raise SystemExit("Refusing to run without MCP_CRASH_ACCEPTANCE=1")
    required = ("MCP_ACCEPTANCE_URL", "MCP_ACCEPTANCE_SERVICE_KEY", "MCP_ACCEPTANCE_ORG_ID")
    if any(not os.environ.get(k) for k in required):
        raise SystemExit("Missing isolated acceptance credentials / disposable org")
    expected_url = "https://aadnwmjzrmbvadszroqt.supabase.co"
    if os.environ["MCP_ACCEPTANCE_URL"].rstrip("/") != expected_url:
        raise SystemExit("Refusing non-acceptance Supabase URL")
    if len(sys.argv) == 4 and sys.argv[1] in ("child", "restart"):
        result = asyncio.run(dispatch(sys.argv[2], int(sys.argv[3]), crash=sys.argv[1] == "child"))
        print(json.dumps(result))
        raise SystemExit(0)

    writes = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            writes.append(json.loads(self.rfile.read(length)))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    approval_id = str(uuid.uuid4())
    db = client()
    org_id = os.environ["MCP_ACCEPTANCE_ORG_ID"]
    try:
        db.table("approvals").insert({
            "id": approval_id, "org_id": org_id, "title": "QA611 synthetic process crash",
            "type": "workflow", "status": "approved",
            "context": {
                "mcp_tool_id": TOOL["id"], "input_sha256": mcp_input_sha256(ARGS),
                "target_digest": mcp_approval_target_digest(TOOL, SERVER),
                "qa": "PR611-crash-acceptance",
            },
        }).execute()
        child = subprocess.run(
            [sys.executable, __file__, "child", approval_id, str(server.server_port)],
            env=os.environ.copy(), capture_output=True, text=True, timeout=45,
        )
        assert child.returncode == 71, f"worker did not die after provider write: {child.returncode} {child.stderr[-800:]}"
        assert writes == [ARGS], f"unexpected first provider writes: {writes}"
        persisted = db.table("approvals").select("consumed_at").eq("id", approval_id).single().execute().data
        assert persisted["consumed_at"], "claim was not durably committed before provider write"
        # A fully separate process starts with new Python state and a new DB client.
        restart = subprocess.run(
            [sys.executable, __file__, "restart", approval_id, str(server.server_port)],
            env=os.environ.copy(), capture_output=True, text=True, timeout=45,
        )
        assert restart.returncode == 0, f"restart process failed: {restart.stderr[-800:]}"
        retry = json.loads(restart.stdout.strip().splitlines()[-1])
        assert retry["status"] == "rejected", retry
        assert writes == [ARGS], "provider was written twice after worker restart"
        print(json.dumps({"result": "PASS", "worker_exit": 71, "provider_writes": len(writes),
                          "durable_claim": True, "restart": "rejected"}))
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
