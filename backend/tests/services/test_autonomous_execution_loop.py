from app.services.autonomous_execution_loop import decide_execution_loop
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep


def plan(*steps, budget=1, used=0):
    return ExecutionPlan(
        plan_id="plan-loop",
        summary="execute task",
        steps=list(steps),
        source="test",
        replan_budget=budget,
        replans_used=used,
    )


def test_continues_to_next_pending_step():
    p = plan(
        ExecutionStep("r1", "read", "read", status="completed"),
        ExecutionStep("r2", "read next", "read", status="pending"),
    )
    d = decide_execution_loop(plan=p, task_state={}, observations=[{"success": True}])
    assert d.action == "continue"
    assert d.next_step_id == "r2"


def test_waiting_approval_wins_over_autonomy():
    p = plan(ExecutionStep("w1", "write", "write", status="pending"))
    d = decide_execution_loop(
        plan=p,
        task_state={"pending_task": {"status": "awaiting_confirm"}},
    )
    assert d.action == "wait_approval"
    assert p.terminal_status == "waiting_for_approval"


def test_failed_read_can_replan_with_same_plan_id_and_budget():
    p = plan(ExecutionStep("r1", "read", "read", status="failed"))
    alt = [ExecutionStep("r2", "alternate read", "read", status="pending")]
    d = decide_execution_loop(plan=p, task_state={}, alternate_read_steps=alt)
    assert d.action == "replan"
    assert d.plan.plan_id == "plan-loop"
    assert d.plan.replans_used == 1
    assert d.plan.revision == 2
    assert d.next_step_id == "r2"


def test_replan_budget_exhaustion_stops():
    p = plan(ExecutionStep("r1", "read", "read", status="failed"), budget=1, used=1)
    d = decide_execution_loop(
        plan=p,
        task_state={},
        alternate_read_steps=[ExecutionStep("r2", "alternate", "read")],
    )
    assert d.action == "stop"
    assert d.reason == "no_safe_replan_available"


def test_failed_write_never_auto_replans():
    p = plan(ExecutionStep("w1", "send", "write", status="failed"))
    d = decide_execution_loop(
        plan=p,
        task_state={},
        alternate_read_steps=[ExecutionStep("r2", "some fallback", "read")],
    )
    assert d.action == "verify"
    assert d.reason == "write_failed_or_uncertain"
    assert d.plan.replans_used == 0


def test_write_cannot_complete_on_accepted_async_only():
    p = plan(ExecutionStep("w1", "send", "write", status="completed"))
    d = decide_execution_loop(
        plan=p,
        task_state={"provider_result_evidence": {"status": "accepted_async"}},
        observations=[{"success": True, "structured": {"provider_status": "accepted_async"}}],
    )
    assert d.action == "verify"
    assert d.reason == "write_unverified"


def test_write_completes_only_with_verified_provider_proof():
    p = plan(ExecutionStep("w1", "send", "write", status="completed"))
    d = decide_execution_loop(
        plan=p,
        task_state={
            "provider_result_evidence": {
                "verification_status": "verified",
                "provider_record_id": "msg-123",
            }
        },
        observations=[{"success": True}],
    )
    assert d.action == "complete"
    assert d.plan.terminal_status == "completed"


def test_iteration_budget_stops_loop():
    p = plan(ExecutionStep("r1", "read", "read", status="pending"))
    d = decide_execution_loop(
        plan=p,
        task_state={},
        iterations_used=8,
        iteration_budget=8,
    )
    assert d.action == "stop"
    assert d.reason == "iteration_budget"


def test_observe_bridge_reconciles_then_decides():
    from app.services.execution_plan_service import ExecutionObservation, decide_after_observations

    p = plan(
        ExecutionStep("r1", "read first", "read", status="running"),
        ExecutionStep("r2", "read second", "read", status="pending"),
    )
    updated, decision = decide_after_observations(
        p,
        [ExecutionObservation("r1", "hubspot", True, "found records")],
        task_state={},
    )
    assert updated.steps[0].status == "completed"
    assert decision["action"] == "continue"
    assert decision["next_step_id"] == "r2"
