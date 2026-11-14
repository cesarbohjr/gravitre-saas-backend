"""PR611 isolated shared write-ledger crash/restart contract test.

This is the real Postgres claim RPC with a synthetic HTTP provider. It does not
pretend to exercise a real HubSpot adapter or the complete connector_chat route.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.tool_types import ToolContext
from app.services.write_invoke_idempotency import build_write_idempotency_key, claim_write_invoke

EXPECTED_URL = "https://aadnwmjzrmbvadszroqt.supabase.co"
QA_ORG_NAME = "Gravitre MCP Acceptance QA"
ACTION = "hubspot.contacts.create"
ARGS = {"qa": "pr611-ledger-process-death", "marker": "disposable"}


def check_env():
    if os.environ.get("MCP_CRASH_ACCEPTANCE") != "1":
        raise SystemExit("Refusing unapproved ledger acceptance run")
    if os.environ.get("MCP_ACCEPTANCE_URL", "").rstrip("/") != EXPECTED_URL:
        raise SystemExit("Refusing non-acceptance database")
    if not os.environ.get("MCP_ACCEPTANCE_SERVICE_KEY") or not os.environ.get("MCP_ACCEPTANCE_ORG_ID"):
        raise SystemExit("Missing QA credentials")


def db_client():
    from supabase import create_client
    return create_client(os.environ["MCP_ACCEPTANCE_URL"], os.environ["MCP_ACCEPTANCE_SERVICE_KEY"])


def key_for(approval_id):
    ctx = ToolContext(
        settings=SimpleNamespace(), client=None,
        org_id=os.environ["MCP_ACCEPTANCE_ORG_ID"],
        actor_id="qa-requester", conversation_id="pr611-qa-conversation",
        turn_id=approval_id, write_idempotency_required=True,
    )
    return build_write_idempotency_key(ctx, ACTION, ARGS)


def dispatch(approval_id, port, *, crash):
    db = db_client()
    key, logical_id = key_for(approval_id)
    result = claim_write_invoke(
        db, org_id=os.environ["MCP_ACCEPTANCE_ORG_ID"],
        idempotency_key=key, invoke_action=ACTION,
        logical_action_id_value=logical_id, lease_seconds=300,
    )
    if crash:
        if result.outcome != "claimed" or not result.claim_token:
            raise AssertionError(f"First claim must be fenced: {result}")
        request = Request(
            f"http://127.0.0.1:{port}/write",
            data=json.dumps(ARGS).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=10) as response:
            assert response.status == 200
        os._exit(71)
    assert result.outcome == "blocked", f"Restart must fail closed: {result}"
    return {"outcome": result.outcome, "status": result.status, "reason": result.reason}


def main():
    check_env()
    if len(sys.argv) == 4 and sys.argv[1] in {"child", "restart"}:
        result = dispatch(sys.argv[2], int(sys.argv[3]), crash=sys.argv[1] == "child")
        print(json.dumps(result))
        return

    writes = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            writes.append(json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0")))))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    db = db_client()
    org_id = os.environ["MCP_ACCEPTANCE_ORG_ID"]
    org = db.table("organizations").select("name").eq("id", org_id).single().execute().data
    if (org or {}).get("name") != QA_ORG_NAME:
        server.shutdown()
        server.server_close()
        raise SystemExit("Refusing non-QA org")
    approval_id = str(uuid.uuid4())
    key, logical_id = key_for(approval_id)
    try:
        child = subprocess.run(
            [sys.executable, __file__, "child", approval_id, str(server.server_port)],
            capture_output=True, text=True, env=os.environ.copy(), timeout=65,
        )
        assert child.returncode == 71, f"Worker crash boundary failed: {child.stderr[-900:]}"
        assert writes == [ARGS], f"Unexpected first side effect count: {writes}"
        rows = (
            db.table("write_invoke_idempotency")
            .select("status,invoke_action,logical_action_id,claim_token")
            .eq("org_id", org_id).eq("idempotency_key", key).execute().data or []
        )
        assert len(rows) == 1 and rows[0]["status"] == "in_progress", rows
        assert rows[0]["invoke_action"] == ACTION and rows[0]["logical_action_id"] == logical_id
        assert rows[0]["claim_token"], "Fenced claim missing"
        restart = subprocess.run(
            [sys.executable, __file__, "restart", approval_id, str(server.server_port)],
            capture_output=True, text=True, env=os.environ.copy(), timeout=65,
        )
        assert restart.returncode == 0, f"Restart failed: {restart.stderr[-900:]}"
        result = json.loads(restart.stdout.strip().splitlines()[-1])
        assert result["outcome"] == "blocked" and result["status"] == "in_progress", result
        assert writes == [ARGS], "Duplicate provider-side effect detected"
        print(json.dumps({
            "result": "PASS", "worker_exit": 71, "ledger_claim": "in_progress",
            "restart": "blocked", "provider_writes": len(writes),
            "actual_provider_readback": False,
        }))
    finally:
        try:
            db.table("write_invoke_idempotency").delete().eq("org_id", org_id).eq("idempotency_key", key).execute()
            remaining = (
                db.table("write_invoke_idempotency").select("id")
                .eq("org_id", org_id).eq("idempotency_key", key).execute().data or []
            )
            if remaining:
                raise RuntimeError("QA ledger cleanup failed")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
