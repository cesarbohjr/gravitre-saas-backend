"""3.0-D durable sessions EXTEND E5 — resume same plan_id, checkpoint before WRITE."""
from __future__ import annotations

from app.services.durable_work_session import (
    CHECKPOINT_KEY,
    DELIVERABLE_KEY,
    DeliverableContract,
    apply_session_complete,
    attach_write_checkpoint,
    checkpoint_before_write,
    load_checkpoint,
    persist_write_approval_patch,
    resume_from_checkpoint,
    session_phase_from_task_state,
    stop_reason,
    strip_secrets,
    verify_before_complete,
)
from app.services.execution_plan_service import (
    ExecutionPlan,
    ExecutionStep,
    reconcile_execution_plan,
)
from app.services.react_write_gate import WRITE_APPROVAL_REQUIRED, block_react_write_execution
from app.services.tool_registry import get_tool_registry


def test_strip_secrets_drops_tokens_not_business_ids():
    cleaned = strip_secrets(
        {
            "property_id": "123",
            "api_key": "sk-live-secret",
            "Authorization": "Bearer abc",
            "nested": {"refresh_token": "r1", "name": "Q3"},
        }
    )
    assert cleaned["property_id"] == "123"
    assert "api_key" not in cleaned
    assert "Authorization" not in cleaned
    assert cleaned["nested"]["name"] == "Q3"
    assert "refresh_token" not in cleaned["nested"]


def test_checkpoint_before_write_strips_secrets_and_keeps_plan_id():
    plan = ExecutionPlan(
        plan_id="plan-d1",
        summary="Create Apollo list",
        steps=[ExecutionStep(step_id="s1", title="write", kind="write")],
        source="test",
        terminal_status="running",
    )
    ck = checkpoint_before_write(
        plan=plan,
        intent="apollo_lists_create",
        inputs={"name": "MSP", "api_token": "hide-me"},
        expected_result="list created",
        approval_id="appr-1",
    )
    payload = ck.as_dict()
    assert payload["plan_id"] == "plan-d1"
    assert payload["phase"] == "WAITING_APPROVAL"
    assert payload["inputs"]["name"] == "MSP"
    assert "api_token" not in payload["inputs"]
    assert payload["approval_id"] == "appr-1"


def test_resume_golden_same_plan_id():
    plan = ExecutionPlan(
        plan_id="plan-resume",
        summary="Write after confirm",
        steps=[ExecutionStep(step_id="w1", title="create list", kind="write")],
        source="test",
        terminal_status="running",
    )
    state = {"execution_plan": plan.as_dict()}
    attach_write_checkpoint(
        state,
        tool_name="apollo_lists_create",
        action="apollo.lists.create",
        args={"name": "MSP"},
    )
    assert session_phase_from_task_state(state) == "WAITING_APPROVAL"
    crashed = {
        CHECKPOINT_KEY: state[CHECKPOINT_KEY],
        "execution_plan": None,
        "pending_task": {"status": "awaiting_confirm", "type": "connector_action"},
    }
    resumed = resume_from_checkpoint(crashed, continue_work=True)
    assert resumed is not None
    assert resumed.plan_id == "plan-resume"
    assert resumed.continuation_of_plan_id == "plan-resume"
    assert resumed.terminal_status == "waiting_for_approval"

    crashed["pending_task"] = {"status": "confirmed"}
    working = resume_from_checkpoint(crashed, continue_work=True)
    assert working is not None
    assert working.plan_id == "plan-resume"
    assert working.terminal_status == "running"


def test_reconcile_resumes_checkpoint_without_minting_plan():
    ck = checkpoint_before_write(
        plan=ExecutionPlan(plan_id="plan-rec", summary="x", steps=[], source="t"),
        intent="write",
        inputs={"name": "A"},
    )
    continued = reconcile_execution_plan(
        message="yes",
        task_state={CHECKPOINT_KEY: ck.as_dict()},
    )
    assert continued.plan_id == "plan-rec"


def test_persist_write_approval_patch_includes_checkpoint():
    plan = ExecutionPlan(
        plan_id="plan-unified",
        summary="Create list",
        steps=[ExecutionStep(step_id="w1", title="write", kind="write")],
        source="unified_turn_live",
        terminal_status="running",
    )
    pending = {
        "type": "connector_action",
        "status": "awaiting_confirm",
        "params": {"invoke_action": "apollo.lists.create", "args": {"name": "MSP"}},
    }
    patch = persist_write_approval_patch(
        {"execution_plan": plan.as_dict()},
        pending_task=pending,
        tool_name="apollo_lists_create",
        action="apollo.lists.create",
        args={"name": "MSP"},
        extra={"recent_user_messages": ["create list"]},
    )
    assert patch["pending_task"]["status"] == "awaiting_confirm"
    ck = load_checkpoint(patch)
    assert ck is not None
    assert ck.plan_id == "plan-unified"
    assert ck.inputs.get("name") == "MSP"
    crashed = {CHECKPOINT_KEY: patch[CHECKPOINT_KEY], "execution_plan": None, "pending_task": pending}
    resumed = resume_from_checkpoint(crashed, continue_work=True)
    assert resumed is not None
    assert resumed.plan_id == "plan-unified"


def test_pending_task_maps_to_waiting_approval():
    phase = session_phase_from_task_state(
        {"pending_task": {"status": "awaiting_confirm", "type": "connector_action"}}
    )
    assert phase == "WAITING_APPROVAL"


def test_write_gate_attaches_checkpoint_without_provider_invoke(monkeypatch):
    monkeypatch.setattr(
        "app.connectors.action_catalog.f1_write_slice.requires_write_approval_always",
        lambda *args, **kwargs: True,
    )
    registry = get_tool_registry()
    plan = ExecutionPlan(
        plan_id="plan-gate",
        summary="create",
        steps=[ExecutionStep(step_id="w1", title="write", kind="write")],
        source="test",
        terminal_status="running",
    )
    task_state = {"execution_plan": plan.as_dict()}
    blocked = block_react_write_execution(
        "apollo_lists_create",
        {"name": "MSP", "access_token": "nope"},
        registry,
        task_state=task_state,
    )
    assert blocked is not None
    assert blocked["error_code"] == WRITE_APPROVAL_REQUIRED
    assert blocked.get("provider_invoked") is not True
    ck = load_checkpoint(task_state)
    assert ck is not None
    assert ck.plan_id == "plan-gate"
    assert "access_token" not in ck.inputs
    assert ck.inputs.get("name") == "MSP"
    assert session_phase_from_task_state(task_state) == "WAITING_APPROVAL"


def test_deliverable_blocks_complete_until_evidence():
    plan = ExecutionPlan(
        plan_id="plan-del",
        summary="investigate",
        steps=[ExecutionStep(step_id="r1", title="read", kind="read")],
        source="test",
        terminal_status="running",
    )
    contract = DeliverableContract(required=True, diagnosis="")
    ok, reason = verify_before_complete(plan=plan, deliverable=contract, observations=[{"success": True}])
    assert ok is False
    assert reason == "deliverable_diagnosis_missing"

    state = {
        "execution_plan": plan.as_dict(),
        DELIVERABLE_KEY: {
            "required": True,
            "diagnosis": "Traffic dropped on /pricing",
            "evidence": ["GA4 sessions -18%"],
            "causes": [],
            "uncertainties": ["attribution window"],
            "actions": ["check Search Console"],
        },
    }
    phase = apply_session_complete(state, observations=[{"success": True, "step_id": "r1"}])
    assert phase == "COMPLETED"
    assert ExecutionPlan.from_dict(state["execution_plan"]).plan_id == "plan-del"


def test_write_unverified_cannot_complete():
    plan = ExecutionPlan(
        plan_id="plan-wv",
        summary="write",
        steps=[ExecutionStep(step_id="w1", title="create", kind="write")],
        source="test",
    )
    ok, reason = verify_before_complete(plan=plan, write_verified=False)
    assert ok is False
    assert reason == "write_unverified"


def test_stop_conditions():
    assert stop_reason(success=True) == "success"
    assert stop_reason(failed=True) == "failure"
    assert stop_reason(iterations_used=3, iteration_budget=3) == "iteration_budget"
    assert stop_reason(tools_used=5, tool_budget=5) == "tool_budget"
    assert stop_reason(elapsed_ms=10_000, time_budget_ms=9_000) == "time_budget"
    assert stop_reason(escalate=True) == "escalation"
    assert stop_reason(iterations_used=1, iteration_budget=3) is None


def test_not_a_second_worker_runtime():
    import app.services.durable_work_session as mod

    assert getattr(mod, "RUNTIME", "e5_execution_plan")
    source = open(mod.__file__, encoding="utf-8").read()
    assert "cowork" not in source.lower()
    assert "second runtime" not in source.lower() or "not a second runtime" in source.lower()
