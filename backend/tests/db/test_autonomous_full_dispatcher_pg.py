"""Disposable actual worker -> handler -> invoke_tool -> PostgreSQL claim -> HTTP receiver.

Kills a worker process either before the effect or after the independent receiver
commits it but before an acknowledgement. Restart uses a fresh worker with the
same durable PostgreSQL ledger. External provider adapter is a test HTTP fixture.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import urllib.request

import pytest
from tests.db.pg_harness import PG_BIN, MIGRATIONS, pg_cluster, requires_pg
from tests.db.test_autonomous_atomic_approval_pg import BOOT, RUN, ORG_A
from tests.db.test_autonomous_independent_write_pg import IndependentFixture
from app.services.tool_types import NormalizedResult

pytestmark = requires_pg
AUDIT = Path(os.environ.get("AUTONOMOUS_WRITE_AUDIT_PATH", "/tmp/autonomous-write-audit")).parent / "full-dispatcher"
MIGRATION = MIGRATIONS / "20261016032018_write_invoke_idempotency.sql"
GRANTS = MIGRATIONS / "20261016032029_write_invoke_idempotency_grants.sql"
ATOMIC = MIGRATIONS / "20261102095000_autonomous_atomic_write_claim.sql"
ACTION = "hubspot.contacts.update"


class SqlRpc:
    def __init__(self, sock: str, port: str, name: str, args: dict):
        self.sock, self.port, self.name, self.args = sock, port, name, args

    def execute(self):
        a = self.args
        def val(name):
            value = a.get(name)
            if value is None:
                return "NULL"
            return "'" + str(value).replace("'", "''") + "'"
        if self.name == "claim_approved_autonomous_write":
            keys = ["p_org_id", "p_run_id", "p_key", "p_invoke_action", "p_logical_action_id", "p_lease_seconds"]
            expr = f"public.claim_approved_autonomous_write({val(keys[0])}::uuid,{val(keys[1])}::uuid,{val(keys[2])},{val(keys[3])},{val(keys[4])},{val(keys[5])}::integer)"
        elif self.name == "finalize_write_invoke_idempotency":
            keys = ["p_org_id", "p_key", "p_claim_token", "p_status", "p_result"]
            expr = f"public.finalize_write_invoke_idempotency({val(keys[0])}::uuid,{val(keys[1])},{val(keys[2])}::uuid,{val(keys[3])},{val(keys[4])}::jsonb)"
        else:
            raise AssertionError("unexpected RPC: " + self.name)
        proc = subprocess.run(
            [str(PG_BIN / "psql"), "-h", self.sock, "-p", self.port,
             "-U", "postgres", "-d", "postgres", "-X", "-q", "-At",
             "-v", "ON_ERROR_STOP=1"],
            input=f"SET ROLE service_role; SELECT {expr}::text;",
            capture_output=True, text=True, check=True,
        )
        return SimpleNamespace(data=json.loads(proc.stdout.strip()))


class PgClient:
    def __init__(self, sock: str, port: str):
        self.sock, self.port = sock, port

    def rpc(self, name, args):
        return SqlRpc(self.sock, self.port, name, args)


def child_worker(sock: str, port: str, receiver_origin: str, stage: str, marker: str):
    from app.services import tool_service
    from app.workers.workflow_worker import process_workflow_run_job
    from app.workers.workflow_queue import WorkflowRunJob
    from app.workflows.registry import StepContext
    from app.workflows import handlers

    client = PgClient(sock, port)
    settings = SimpleNamespace(
        write_authority_mode="enforce", write_invoke_idempotency_enabled=True,
        private_connector_runtime_enabled=False,
    )
    run = {
        "id": RUN, "status": "running", "triggered_by": "actor",
        "definition_snapshot": {"steps": []},
        "parameters": {"_autonomous_run": True},
        "environment": "acceptance",
    }
    def executor(ctx, args):
        if stage == "before" and not Path(marker).exists():
            Path(marker).write_text("attempted")
            while True:
                time.sleep(.1)
        body = json.dumps({"cap": "autonomous-full-dispatcher"}).encode()
        req = urllib.request.Request(
            receiver_origin + "/write", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            assert response.status == 204
        return NormalizedResult(success=True, action=ACTION, data={"id": "contact-1"})

    def execute(**kwargs):
        step = StepContext(
            settings=kwargs["settings"], org_id=kwargs["org_id"],
            user_id=kwargs["user_id"], run_id=kwargs["run_id"],
            environment_name=kwargs["environment_name"], step_id="write-1",
            step_type="invoke_tool", step_index=0, config={},
            parameters=kwargs["parameters"], step_outputs={},
            client=kwargs["client"], is_dry_run=False,
        )
        result = handlers._invoke_canvas_registered_tool(step, ACTION, {"id": "contact-1"})
        assert result.success
        return ("completed", [], [], False)

    row = {"required_approvals": 1, "approval_status": "approved",
           "parameters": {}, "definition_snapshot": {}}
    with (
        patch("app.workers.workflow_worker.get_supabase_client", return_value=client),
        patch("app.workers.workflow_worker.get_run_with_steps", return_value=run),
        patch("app.workers.workflow_worker.execute_workflow_steps", side_effect=execute),
        patch("app.services.canvas_write_gate.bind_f1_write_hmac_context",
              side_effect=lambda **k: (k["tool_ctx"], k["params"])),
        patch("app.services.sealed_read_execution.bind_read_preflight",
              side_effect=lambda ctx, act, params, **kw: (ctx, params, None)),
        patch("app.services.canvas_write_gate.require_approved_authority_run", return_value=row),
        patch("app.services.conversation_write_guard.assert_org_write_allowed"),
        patch("app.services.agent_interrupt_service.enforce_interrupt"),
        patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda ctx,act,params:params),
        patch.object(tool_service, "_resolve_tool_executor", return_value=executor),
        patch("app.services.hipaa_service.enforce_hipaa_for_tool_invoke"),
        patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits"),
        patch.object(tool_service, "assert_agent_tool_permission"),
        patch.object(tool_service, "_write_tool_audit"),
        patch("app.services.workflow_approval_scope.block_invoke_by_approval_scope", return_value=None),
        patch("app.services.compensation_service.should_track_compensation", return_value=False),
        patch("app.services.execution_outcome.finalize_execution_outcome"),
        patch("app.workers.workflow_queue.assert_current_workflow_claim_live"),
    ):
        job = WorkflowRunJob(run_id=RUN, org_id=ORG_A, workflow_id="wf-1")
        return process_workflow_run_job(settings, json.dumps(job.__dict__))


def _start(pg, origin, stage, marker):
    cmd = [sys.executable, "-c",
           "from tests.db.test_autonomous_full_dispatcher_pg import child_worker; "
           "import sys; child_worker(*sys.argv[1:])",
           str(pg.sock), pg.port, origin, stage, str(marker)]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


@pytest.mark.parametrize("case,expected", [("crash_before_effect", 0), ("crash_after_effect", 1)])
def test_real_worker_kill_restart_blocks_duplicate_dispatch(tmp_path, case, expected):
    with pg_cluster(BOOT, MIGRATION.read_text(), GRANTS.read_text(), ATOMIC.read_text()) as pg:
        receiver = IndependentFixture(
            tmp_path / (case + ".sqlite3"), b"<h1>isolated</h1>",
            capability="autonomous-full-dispatcher",
        )
        marker = tmp_path / "before-provider"
        receiver.hold = expected == 1
        proc = _start(pg, receiver.origin, "before" if expected == 0 else "after", marker)
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if pg.value("SELECT count(*) FROM public.write_invoke_idempotency") == "1":
                    if (expected == 0 and marker.exists()) or (expected == 1 and receiver.writes == 1):
                        break
                if proc.poll() is not None:
                    raise AssertionError("worker exited before controlled kill: " + proc.communicate()[1][-2500:])
                time.sleep(.1)
            assert (marker.exists() if expected == 0 else receiver.writes == 1)
            proc.kill()
            proc.communicate(timeout=5)
            pg.psql("""UPDATE public.write_invoke_idempotency
                SET lease_expires_at=now()-interval '1 minute'
                WHERE org_id='""" + ORG_A + """';""")
            receiver.hold = False
            restarted = _start(pg, receiver.origin, "after", marker)
            try:
                _, stderr = restarted.communicate(timeout=20)
                assert restarted.returncode == 0, stderr[-2500:]
            finally:
                if restarted.poll() is None:
                    restarted.kill()
                    restarted.communicate(timeout=5)
            assert receiver.writes == expected
            assert pg.value("SELECT status FROM public.write_invoke_idempotency") == "uncertain"
            AUDIT.mkdir(parents=True, exist_ok=True)
            (AUDIT / (case + ".json")).write_text(json.dumps({
                "case": case, "observed_committed_writes": receiver.writes,
                "expected_committed_writes": expected,
                "unauthorized_or_duplicate_writes": 0,
                "claim_status": "uncertain", "worker_killed": True,
                "worker_restarted": True, "passed": True,
            }, indent=2))
        finally:
            receiver.hold = False
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)
            receiver.close()
