"""Production workflow context must not drop autonomous write fencing."""
from types import SimpleNamespace
from app.services.tool_service import tool_context_from_step


def _step(parameters, run_id="run-123"):
    return SimpleNamespace(
        parameters=parameters, settings=SimpleNamespace(), client=None,
        org_id="org-123", user_id="actor-123",
        environment_name="acceptance", run_id=run_id,
        plan_id=None, conversation_id=None,
        step_id="step-123", step_type="invoke_tool",
        config={"connector_id": "fixture-connector"},
    )


def test_autonomous_workflow_keeps_strict_atomic_write_guard():
    ctx = tool_context_from_step(_step({"_autonomous_run": True}))
    assert ctx.autonomous_write_guarded is True
    assert ctx.run_id == "run-123"
    assert ctx.org_id == "org-123"


def test_ordinary_workflow_does_not_gain_autonomous_flag():
    assert tool_context_from_step(_step({})).autonomous_write_guarded is False


def test_autonomous_context_without_durable_run_does_not_claim_approval():
    assert tool_context_from_step(_step({"_autonomous_run": True}, run_id=None)).autonomous_write_guarded is False
