"""Worker -> workflow handler -> production tool context acceptance.

This test deliberately uses the actual worker entrypoint and workflow handler.
It verifies the guarded invoke boundary, not external provider exactly-once delivery.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.workers.workflow_worker import process_workflow_run_job
from app.workers.workflow_queue import WorkflowRunJob
from app.workflows.registry import StepContext


def test_worker_dispatch_preserves_autonomous_guard_to_handler_and_invoker():
    from app.workflows import handlers
    import json

    run_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    org_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    action = "hubspot.contacts.update"
    run = {
        "id": run_id, "status": "running", "triggered_by": "actor",
        "definition_snapshot": {"steps": []},
        "parameters": {"_autonomous_run": True},
        "environment": "acceptance",
    }
    seen = []

    def execute(**kwargs):
        step = StepContext(
            settings=kwargs["settings"], org_id=kwargs["org_id"],
            user_id=kwargs["user_id"], run_id=kwargs["run_id"],
            environment_name=kwargs["environment_name"],
            step_id="step-1", step_type="invoke_tool", step_index=0,
            config={}, parameters=kwargs["parameters"], step_outputs={},
            client=kwargs["client"], is_dry_run=False,
        )
        handlers._invoke_canvas_registered_tool(step, action, {"id": "contact-1"})
        return ("completed", [], [], False)

    def invoke(ctx, act, params):
        seen.append((ctx.autonomous_write_guarded, ctx.run_id, ctx.org_id, act))
        return SimpleNamespace(success=True)

    settings = SimpleNamespace()
    job = WorkflowRunJob(run_id=run_id, org_id=org_id, workflow_id="wf-1")
    with (
        patch("app.workers.workflow_worker.get_supabase_client", return_value=MagicMock()),
        patch("app.workers.workflow_worker.get_run_with_steps", return_value=run),
        patch("app.workers.workflow_worker.execute_workflow_steps", side_effect=execute),
        patch("app.services.canvas_write_gate.bind_f1_write_hmac_context",
              side_effect=lambda **k: (k["tool_ctx"], k["params"])),
        patch("app.services.sealed_read_execution.bind_read_preflight",
              side_effect=lambda ctx, act, params, **kw: (ctx, params, None)),
        patch.object(handlers, "invoke_tool", side_effect=invoke),
    ):
        assert process_workflow_run_job(settings, json.dumps(job.__dict__)) is True
    assert seen == [(True, run_id, org_id, action)]
