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


def test_bind_finished_work_report_from_observations():
    from app.services.durable_work_session import (
        DELIVERABLE_KEY,
        WORK_ARTIFACTS_KEY,
        bind_finished_work,
        execution_result_from_finished_work,
        reconstruct_execution_result,
    )

    plan = ExecutionPlan(
        plan_id="plan-art-1",
        summary="Pipeline sample",
        steps=[ExecutionStep(step_id="r1", title="list deals", kind="read")],
        source="operational_read",
        terminal_status="completed",
    )
    state = {
        "execution_plan": plan.as_dict(),
        "execution_observations": [
            {
                "step_id": "r1",
                "observation_id": "obs-1",
                "success": True,
                "summary": "From the connected CRM I received 2 deals in this sample.",
                "structured": {
                    "action_key": "hubspot.deals.list",
                    "result_count": 2,
                    "provider_invoked": True,
                },
            }
        ],
    }
    bound = bind_finished_work(state, body=state["execution_observations"][0]["summary"])
    contract = bound[DELIVERABLE_KEY]
    artifacts = bound[WORK_ARTIFACTS_KEY]
    assert contract["diagnosis"].startswith("From the connected CRM")
    assert any("hubspot.deals.list" in line for line in contract["evidence"])
    assert artifacts[-1]["kind"] == "executive_report"
    assert artifacts[-1]["metadata"]["plan_id"] == "plan-art-1"
    assert "$" not in artifacts[-1]["preview"]
    payload = execution_result_from_finished_work(bound)
    assert payload is not None
    assert payload["entity_type"] == "report"
    kinds = {row["kind"] for row in (payload.get("artifacts") or [])}
    assert "executive_report" in kinds or "report" in kinds or "document" in kinds
    again = reconstruct_execution_result(bound)
    assert again is not None
    assert again["entity_id"] == payload["entity_id"]
    assert again["structured"]["plan_id"] == "plan-art-1"


def test_bind_finished_work_skips_without_successful_observation():
    from app.services.durable_work_session import bind_finished_work, reconstruct_execution_result

    bound = bind_finished_work({"execution_observations": [{"success": False, "summary": "no"}]})
    assert bound.get("work_artifacts")
    assert bound["work_artifacts"][-1]["metadata"]["outcome"] == "failed"
    rebuilt = reconstruct_execution_result(bound)
    assert rebuilt is not None
    assert rebuilt["success"] is False


def test_reconstruct_does_not_require_provider_reinvoke():
    from app.services.durable_work_session import reconstruct_execution_result

    stored = {
        "execution_plan": {"plan_id": "plan-resume", "terminal_status": "completed", "steps": []},
        "work_artifacts": [
            {
                "artifact_id": "report:plan-resume",
                "kind": "report",
                "title": "CRM read",
                "preview": "2 deals",
                "metadata": {
                    "plan_id": "plan-resume",
                    "outcome": "completed",
                    "observation_ids": ["obs-9"],
                    "code": "Outcome: completed\n2 deals\n- hubspot.deals.list rows=2 obs=obs-9",
                },
            }
        ],
    }
    rebuilt = reconstruct_execution_result(stored)
    assert rebuilt is not None
    assert rebuilt["success"] is True
    assert rebuilt["entity_id"] == "plan-resume"
    assert "hubspot.deals.list" in str(rebuilt["structured"]["content"])


def test_reconstruct_returns_persisted_claim_labels():
    from app.services.durable_work_session import reconstruct_execution_result

    stored = {
        "execution_plan": {"plan_id": "plan-diag", "terminal_status": "completed", "steps": []},
        "diagnostic_conclusion": {
            "labels": [{"text": "HubSpot returned 2 deals.", "label": "FACT", "observation_id": "obs-1"}],
            "missing_sources": ["Google Analytics is not connected."],
            "provider_reinvoked": False,
        },
        "work_artifacts": [
            {
                "artifact_id": "report:plan-diag",
                "kind": "report",
                "title": "Diagnostic",
                "preview": "HubSpot returned 2 deals.",
                "metadata": {"plan_id": "plan-diag", "outcome": "completed", "code": "HubSpot returned 2 deals."},
            }
        ],
    }
    rebuilt = reconstruct_execution_result(stored)
    assert rebuilt is not None
    assert rebuilt["structured"]["claim_labels"][0]["label"] == "FACT"
    assert rebuilt["structured"]["missing_sources"]
    assert rebuilt["structured"]["provider_reinvoked"] is False
