"""Phase E5 — ExecutionPlan convergence benchmarks."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.execution_plan_adapters import (
    bridge_offered_action_with_plan,
    bridge_pending_task_with_plan,
    enrich_task_state_patch,
    execution_plan_from_connector_action,
    execution_plan_from_offered_action,
    execution_plan_from_orchestration_steps,
)
from app.services.execution_plan_service import (
    ExecutionPlan,
    ExecutionStep,
    reconcile_execution_plan,
    replan_execution_plan,
)
from app.services.offered_action_continuation import (
    extract_offered_action,
    resolve_offered_action_turn,
)

OFFER = (
    "I don't have enough information yet to say what needs attention. "
    "If you want, I can check connector health, recent workflow runs, or org analytics."
)

def test_scenario_a_simple_read_compose_plan() -> None:
    plan = reconcile_execution_plan(message="Check my GA4 traffic.", task_state={})
    assert plan.plan_id
    assert plan.execution_strategy == "ANSWER_ONLY" or plan.steps


def test_scenario_b_parallel_read_plan() -> None:
    plan = reconcile_execution_plan(
        message="Check GA4 and Search Console and tell me how the site is performing.",
        task_state={},
        connected_integrations=["google_analytics", "google_search_console"],
    )
    assert plan.source == "cross_source_analytics_replanner"
    read_steps = [s for s in plan.steps if s.kind == "read"]
    assert len(read_steps) == 2
    assert plan.execution_strategy == "PARALLEL"


def test_scenario_c_yes_preserves_plan_lineage() -> None:
    offered = extract_offered_action(OFFER)
    assert offered is not None
    plan, pending_action, bridged = bridge_offered_action_with_plan(offered.as_dict())
    turn1_state = {
        "offered_action": bridged,
        "execution_plan": plan.as_dict(),
        "pending_action": pending_action.as_dict(),
    }
    continued = reconcile_execution_plan(message="yes", task_state=turn1_state)
    assert continued.plan_id == plan.plan_id
    assert continued.continuation_of_plan_id == plan.plan_id
    assert continued.terminal_status == "running"


def test_scenario_c_yes_executes_offered_read() -> None:
    offered = extract_offered_action(OFFER)
    assert offered is not None
    plan, pending_action, bridged = bridge_offered_action_with_plan(offered.as_dict())
    decision = resolve_offered_action_turn(
        "yes",
        task_state={
            "offered_action": bridged,
            "execution_plan": plan.as_dict(),
            "pending_action": pending_action.as_dict(),
        },
    )
    assert decision.kind == "execute_read"
    assert decision.offered is not None
    assert decision.offered.execution_plan_id == plan.plan_id


def test_pending_task_bridge_projects_execution_plan_id() -> None:
    pending = {
        "type": "connector_action",
        "status": "awaiting_confirm",
        "action": "gmail.send",
        "connector_id": "gmail",
        "requires_approval": True,
    }
    plan, pending_action, projected = bridge_pending_task_with_plan(pending)
    assert projected["execution_plan_id"] == plan.plan_id
    assert projected["_projection"] is True
    assert pending_action.plan_id == plan.plan_id
    assert plan.terminal_status == "waiting_for_approval"


def test_enrich_task_state_patch_bridges_pending_task() -> None:
    patch = enrich_task_state_patch(
        {
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_confirm",
                "action": "gmail.send",
                "connector_id": "gmail",
            }
        }
    )
    assert isinstance(patch.get("execution_plan"), dict)
    assert patch["execution_plan"]["plan_id"]
    assert patch["pending_task"]["execution_plan_id"] == patch["execution_plan"]["plan_id"]


def test_connector_action_adapter() -> None:
    cap = ConnectorActionPlan(
        tool_name="gmail_send",
        invoke_action="gmail.send",
        integration="gmail",
        kind="write",
        label="Send email",
        requires_approval=True,
    )
    plan = execution_plan_from_connector_action(cap)
    assert plan.steps[0].connector_id == "gmail"
    assert plan.terminal_status == "waiting_for_approval"


def test_explicit_replan_preserves_lineage() -> None:
    original = ExecutionPlan(
        plan_id="plan-original",
        summary="Analyze pipeline",
        steps=[],
        source="test",
    )
    revised = replan_execution_plan(
        original,
        new_steps=[],
        reason="partial_failure",
        evidence={"failed_step": "read_ga4"},
    )
    assert revised.plan_id == "plan-original"
    assert revised.parent_plan_id == "plan-original"
    assert revised.revision == 2
    assert revised.replan_reason == "partial_failure"


def test_reconcile_reuses_existing_plan_id_for_pending_task() -> None:
    plan_id = "stable-plan-123"
    plan = reconcile_execution_plan(
        message="yes",
        task_state={
            "execution_plan": {
                "plan_id": plan_id,
                "summary": "Pending connector action",
                "source": "pending_task",
                "terminal_status": "pending",
                "steps": [
                    {
                        "step_id": "pending_primary",
                        "title": "gmail.send",
                        "kind": "write",
                        "status": "pending",
                    }
                ],
            },
            "pending_task": {
                "status": "awaiting_confirm",
                "action": "gmail.send",
                "execution_plan_id": plan_id,
            },
        },
    )
    assert plan.plan_id == plan_id
    assert plan.continuation_of_plan_id == plan_id


def test_offered_action_plan_has_parallel_group() -> None:
    offered = extract_offered_action(OFFER)
    assert offered is not None
    plan = execution_plan_from_offered_action(offered.as_dict())
    read_steps = [s for s in plan.steps if s.kind == "read"]
    assert len(read_steps) >= 3
    assert all(s.meta.get("parallel_group") == "offered_read_tools" for s in read_steps)


def test_plan_ids_are_uuid_like() -> None:
    plan = reconcile_execution_plan(message="hello", task_state={})
    UUID(plan.plan_id)


@pytest.mark.asyncio
async def test_scenario_c_execute_offered_read_updates_plan() -> None:
    from app.services.offered_action_continuation import execute_offered_read

    offered = extract_offered_action(OFFER)
    assert offered is not None
    plan, pending_action, bridged = bridge_offered_action_with_plan(offered.as_dict())
    offered.execution_plan_id = plan.plan_id
    offered.pending_action_id = pending_action.pending_action_id

    async def _fake_tools(requested: list[str], *args, **kwargs):
        return [{"name": requested[0], "output": {"connectors": []}}]

    with patch(
        "app.services.assistant_tools.run_assistant_tools",
        new=AsyncMock(side_effect=_fake_tools),
    ):
        executed = await execute_offered_read(
            offered,
            org_id="org-test",
            settings=object(),
        )
    assert isinstance(executed.get("execution_plan"), dict)
    assert executed["execution_plan"]["plan_id"] == plan.plan_id
    assert executed["execution_plan"]["terminal_status"] in {"completed", "partial", "failed"}
    assert executed.get("execution_observations")


def test_orchestration_adapter_multi_step() -> None:
    from app.services.chat_orchestration_service import OrchestrationStep

    steps = [
        OrchestrationStep(
            step_id="s1",
            segment="send",
            label="Send email",
            kind="write",
            supported=True,
            requires_approval=True,
            plan=ConnectorActionPlan(
                tool_name="gmail_send",
                invoke_action="gmail.send",
                integration="gmail",
                kind="write",
                label="Send email",
            ),
        )
    ]
    plan = execution_plan_from_orchestration_steps(steps, summary="Send approved email")
    assert plan.steps[0].action_key == "gmail.send"
    assert plan.execution_strategy == "SEQUENTIAL"


def test_authority_blocks_pending_task_redefining_plan() -> None:
    """Once canonical, pending_task ingress must not recreate ExecutionPlan."""
    canonical = {
        "plan_id": "canonical-1",
        "summary": "Send email",
        "source": "connector_action",
        "terminal_status": "waiting_for_approval",
        "revision": 1,
        "steps": [
            {
                "step_id": "connector_primary",
                "title": "Send email",
                "kind": "write",
                "status": "pending",
            }
        ],
    }
    patch = enrich_task_state_patch(
        {
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_confirm",
                "action": "gmail.send",
                "connector_id": "gmail",
            }
        },
        current_state={"execution_plan": canonical},
    )
    assert "execution_plan" not in patch
    assert patch["pending_task"]["execution_plan_id"] == "canonical-1"
    assert patch["pending_task"]["_projection"] is True


def test_scenario_d_write_approval_bridge() -> None:
    pending = {
        "type": "connector_action",
        "status": "awaiting_confirm",
        "action": "gmail.send",
        "connector_id": "gmail",
        "requires_approval": True,
        "params": {"to": "stephanie@example.com", "subject": "Gravitre test", "body": "hello Steph"},
    }
    plan, pending_action, projected = bridge_pending_task_with_plan(pending)
    assert plan.terminal_status == "waiting_for_approval"
    assert pending_action.kind == "approval"
    assert pending_action.plan_id == plan.plan_id
    continued = reconcile_execution_plan(
        message="yes",
        task_state={
            "execution_plan": plan.as_dict(),
            "pending_task": projected,
            "pending_action": pending_action.as_dict(),
        },
    )
    assert continued.plan_id == plan.plan_id


def test_scenario_e_react_execution_strategy() -> None:
    from app.services.react_execution_strategy import (
        finalize_react_execution_plan,
        prepare_react_execution_plan,
        react_observation_from_tool_call,
    )

    runtime = prepare_react_execution_plan(message="Find contacts then summarize", task_state={})
    plan_id = runtime.plan.plan_id
    assert runtime.plan.execution_strategy == "REACT"
    react_observation_from_tool_call(
        runtime,
        iteration=1,
        tool_name="search_contacts",
        observation={"success": True, "message": "found 3"},
        elapsed_ms=120,
    )
    finalized, observations = finalize_react_execution_plan(
        runtime,
        react_status="completed",
        answer="Summary here",
    )
    assert finalized.plan_id == plan_id
    assert finalized.execution_strategy == "REACT"
    assert observations
    assert observations[0].step_id


def test_scenario_f_voice_write_equivalence() -> None:
    from app.services.voice_plan_equivalence import plans_semantically_equivalent, reconcile_for_modality

    msg = "Send Stephanie an email with subject Gravitre test and body hello Steph."
    text_plan = reconcile_for_modality(msg, spoken_mode=False)
    voice_plan = reconcile_for_modality(msg, spoken_mode=True)
    assert plans_semantically_equivalent(text_plan, voice_plan)


def test_scenario_g_workflow_bridge() -> None:
    from app.services.workflow_execution_strategy import (
        execution_plan_step_for_workflow,
        workflow_observation,
    )

    plan = execution_plan_step_for_workflow(
        workflow_id="wf-123",
        workflow_name="Daily sync",
        objective="Run daily sync workflow",
    )
    assert plan.steps[0].kind == "workflow"
    assert plan.execution_strategy == "WORKFLOW"
    obs = workflow_observation(
        plan_id=plan.plan_id,
        step_id=plan.steps[0].step_id,
        workflow_id="wf-123",
        result={"status": "queued", "runId": "run-1"},
    )
    assert obs.success is True
    assert obs.source == "workflow"


def test_scenario_h_agent_delegation_lineage() -> None:
    from app.services.agent_delegation_strategy import (
        create_child_plan_for_delegation,
        delegation_observation,
        execution_plan_with_agent_delegation_step,
    )

    parent = ExecutionPlan(
        plan_id="parent-1",
        summary="Investigate pipeline decline",
        steps=[],
        source="test",
    )
    parent = execution_plan_with_agent_delegation_step(
        parent,
        agent_id="sales-analyst",
        objective="Analyze sales pipeline",
    )
    child = create_child_plan_for_delegation(
        parent,
        parent_step_id=parent.steps[0].step_id,
        agent_id="sales-analyst",
        objective="Analyze sales pipeline",
    )
    assert child.parent_plan_id == "parent-1"
    obs = delegation_observation(
        parent_plan_id=parent.plan_id,
        parent_step_id=parent.steps[0].step_id,
        child_plan=child,
        result={"summary": "Pipeline down 12%"},
    )
    assert obs.structured["child_plan_id"] == child.plan_id


def test_scenario_i_replan_revision_increment() -> None:
    plan = ExecutionPlan(
        plan_id="plan-1",
        summary="Cross-source analytics",
        steps=[
            ExecutionStep(step_id="read_ga4", title="GA4", kind="read", connector_id="google_analytics", status="failed"),
        ],
        source="test",
        revision=1,
    )
    revised = replan_execution_plan(
        plan,
        new_steps=[
            ExecutionStep(step_id="read_ga4_retry", title="GA4 retry", kind="read", connector_id="google_analytics"),
        ],
        reason="read_failure",
    )
    assert revised.plan_id == "plan-1"
    assert revised.revision == 2
    assert revised.replan_reason == "read_failure"


def test_scenario_j_failure_terminal_state() -> None:
    from app.services.react_execution_strategy import finalize_react_execution_plan, prepare_react_execution_plan

    runtime = prepare_react_execution_plan(message="Check systems", task_state={})
    runtime.record_tool_observation(
        step_id="react_1_connector_status",
        tool_name="connector_status",
        observation={"success": False, "error": "timeout"},
        elapsed_ms=8000,
    )
    finalized, _ = finalize_react_execution_plan(runtime, react_status="error")
    assert finalized.terminal_status in {"failed", "partial", "blocked"}


def test_strategic_current_plan_not_executable() -> None:
    plan = reconcile_execution_plan(
        message="hello",
        task_state={
            "current_plan": {
                "summary": "Strategic outline",
                "plan_kind": "strategic_reasoning",
                "executable": False,
                "steps": [{"step_id": "1", "title": "Think"}],
            }
        },
    )
    assert plan.source != "current_plan" or plan.execution_strategy == "ANSWER_ONLY"


def test_detect_stalled_running_plan() -> None:
    from app.services.execution_plan_service import detect_stalled_plan

    plan = ExecutionPlan(plan_id="p", summary="x", steps=[], source="test", terminal_status="running")
    assert detect_stalled_plan(plan, pending_action=None, has_active_execution=False) == "STALLED"


def test_stale_pending_task_cannot_override_canonical_step() -> None:
    from app.services.execution_dispatch import resolve_executable_connector_plan

    plan = ExecutionPlan(
        plan_id="plan-x",
        summary="Send email",
        source="test",
        steps=[
            ExecutionStep(
                step_id="write_email",
                title="Send email",
                kind="write",
                connector_id="gmail",
                action_key="gmail.send",
                meta={"args": {"to": "stephanie@example.com", "subject": "Gravitre test", "body": "hello Steph"}},
            )
        ],
    )
    state = {
        "execution_plan": plan.as_dict(),
        "pending_task": {
            "type": "connector_action",
            "status": "awaiting_confirm",
            "execution_plan_id": "plan-x",
            "_projection": True,
            "params": {
                "integration": "hubspot",
                "invoke_action": "hubspot.contacts.create",
                "args": {"email": "attacker@example.com"},
            },
        },
    }
    resolved = resolve_executable_connector_plan(state)
    assert resolved is not None
    assert resolved.integration == "gmail"
    assert resolved.invoke_action == "gmail.send"
    assert resolved.args.get("to") == "stephanie@example.com"
    assert resolved.args.get("email") != "attacker@example.com"


def test_write_gate_plan_action_ignores_mutated_pending() -> None:
    from app.services.chat_connector_execution_service import ChatConnectorExecutionService
    from unittest.mock import MagicMock

    svc = ChatConnectorExecutionService.__new__(ChatConnectorExecutionService)
    svc._registry = MagicMock()
    svc.settings = MagicMock()
    svc._sanitize_plan_message_bodies = lambda p: p
    plan = ExecutionPlan(
        plan_id="plan-x",
        summary="Send email",
        source="test",
        steps=[
            ExecutionStep(
                step_id="write_email",
                title="Send email",
                kind="write",
                connector_id="gmail",
                action_key="gmail.send",
                meta={"args": {"to": "stephanie@example.com", "body": "hello Steph"}},
            )
        ],
    )
    out = svc.plan_action(
        "yes",
        connected_integrations=["gmail"],
        task_state={
            "execution_plan": plan.as_dict(),
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_confirm",
                "params": {
                    "integration": "slack",
                    "invoke_action": "slack.chat.postMessage",
                    "args": {"channel": "#wrong"},
                },
            },
        },
    )
    assert out is not None
    assert out.integration == "gmail"
    assert out.invoke_action == "gmail.send"


def test_strategic_plan_cannot_dispatch() -> None:
    import pytest
    from app.services.execution_dispatch import StrategicPlanNotExecutable, assert_plan_is_dispatchable

    with pytest.raises(StrategicPlanNotExecutable):
        assert_plan_is_dispatchable(
            {"plan_kind": "strategic_reasoning", "executable": False, "steps": [{"step_id": "1"}]}
        )


def test_dispatch_requires_plan_and_step_ids() -> None:
    from app.services.execution_dispatch import CanonicalDispatchError, dispatch_execution_step

    step = ExecutionStep(step_id="s1", title="Read", kind="read")
    env = dispatch_execution_step(plan_id="p1", step_id="s1", step=step)
    assert env["attribution"] == {"plan_id": "p1", "step_id": "s1"}
    try:
        dispatch_execution_step(plan_id="", step_id="s1", step=step)
        raise AssertionError("expected CanonicalDispatchError")
    except CanonicalDispatchError:
        pass


def test_child_cannot_mutate_parent_directly() -> None:
    from app.services.agent_delegation_strategy import create_child_plan_for_delegation
    from app.services.execution_dispatch import apply_child_result_to_parent

    parent = ExecutionPlan(
        plan_id="parent-1",
        summary="Investigate",
        steps=[ExecutionStep(step_id="delegate_1", title="Delegate", kind="agent_delegation")],
        source="test",
    )
    child = create_child_plan_for_delegation(
        parent, parent_step_id="delegate_1", agent_id="sales", objective="Analyze"
    )
    child.objective = "HACKED PARENT OBJECTIVE"
    child.summary = "HACKED"
    restored = apply_child_result_to_parent(
        parent,
        parent_step_id="delegate_1",
        child=child,
        observation_structured={"summary": "child done"},
    )
    assert restored.objective == "Investigate" or restored.summary == "Investigate"
    assert restored.plan_id == "parent-1"
    assert child.parent_step_id == "delegate_1"


def test_workflow_returns_to_parent_step() -> None:
    from app.services.workflow_execution_strategy import (
        apply_workflow_result_to_plan,
        execution_plan_step_for_workflow,
    )

    plan = execution_plan_step_for_workflow(workflow_id="wf-1", workflow_name="Sync")
    updated = apply_workflow_result_to_plan(
        plan, step_id=plan.steps[0].step_id, result={"status": "completed"}
    )
    assert updated.terminal_status == "completed"
    assert updated.steps[0].status == "completed"


def test_strategy_observations_include_plan_and_step() -> None:
    from app.services.react_execution_strategy import (
        prepare_react_execution_plan,
        react_observation_from_tool_call,
    )
    from app.services.workflow_execution_strategy import workflow_observation
    from app.services.agent_delegation_strategy import delegation_observation, create_child_plan_for_delegation

    runtime = prepare_react_execution_plan(message="lookup", task_state={})
    obs = react_observation_from_tool_call(
        runtime, iteration=1, tool_name="search", observation={"success": True}
    )
    assert obs.plan_id == runtime.plan.plan_id
    assert obs.step_id

    wf = workflow_observation(plan_id="p", step_id="s", workflow_id="w", result={"ok": True})
    assert wf.plan_id == "p" and wf.step_id == "s"

    parent = ExecutionPlan(
        plan_id="p1",
        summary="p",
        steps=[ExecutionStep(step_id="d1", title="d", kind="agent_delegation")],
        source="t",
    )
    child = create_child_plan_for_delegation(parent, parent_step_id="d1", agent_id="a", objective="o")
    dobs = delegation_observation(
        parent_plan_id="p1", parent_step_id="d1", child_plan=child, result={"summary": "ok"}
    )
    assert dobs.plan_id == "p1" and dobs.step_id == "d1"


def test_e5_latency_baseline_deterministic_adapters() -> None:
    import time

    from app.services.execution_dispatch import dispatch_execution_step, resolve_executable_connector_plan
    from app.services.execution_plan_service import reconcile_execution_plan
    from app.services.pending_action_service import pending_action_from_offered
    from app.services.react_execution_strategy import prepare_react_execution_plan, finalize_react_execution_plan
    from app.services.workflow_execution_strategy import execution_plan_step_for_workflow
    from app.services.agent_delegation_strategy import create_child_plan_for_delegation

    samples: dict[str, list[float]] = {k: [] for k in (
        "reconcile", "pending_action", "dispatch", "react", "workflow", "agent"
    )}
    for _ in range(40):
        t0 = time.perf_counter()
        reconcile_execution_plan(message="Check my GA4 traffic.", task_state={})
        samples["reconcile"].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        pending_action_from_offered(offered_id="o1", plan_id="p1", scope=["analytics"], tools=["analytics"])
        samples["pending_action"].append((time.perf_counter() - t0) * 1000)

        step = ExecutionStep(step_id="s", title="t", kind="read", action_key="x")
        t0 = time.perf_counter()
        dispatch_execution_step(plan_id="p", step_id="s", step=step)
        samples["dispatch"].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        rt = prepare_react_execution_plan(message="multi step", task_state={})
        finalize_react_execution_plan(rt, react_status="completed", answer="ok")
        samples["react"].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        execution_plan_step_for_workflow(workflow_id="w")
        samples["workflow"].append((time.perf_counter() - t0) * 1000)

        parent = ExecutionPlan(plan_id="p", summary="s", steps=[ExecutionStep(step_id="d", title="d", kind="agent_delegation")], source="t")
        t0 = time.perf_counter()
        create_child_plan_for_delegation(parent, parent_step_id="d", agent_id="a", objective="o")
        samples["agent"].append((time.perf_counter() - t0) * 1000)

        resolve_executable_connector_plan({"execution_plan": parent.as_dict()})

    def pct(vals: list[float], p: float) -> float:
        ordered = sorted(vals)
        idx = min(len(ordered) - 1, max(0, int(round((p / 100) * (len(ordered) - 1)))))
        return ordered[idx]

    for name, vals in samples.items():
        assert pct(vals, 95) < 50.0, f"{name} p95 too high: {pct(vals, 95):.3f}ms"
        print(f"e5_latency {name} p50={pct(vals, 50):.3f}ms p95={pct(vals, 95):.3f}ms")
