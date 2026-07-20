"""Multi-step AI Chat workflow E2E scenarios using ChatOrchestrationService."""
from __future__ import annotations

import csv
import json
import uuid
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from unittest.mock import patch

from app.services.chat_orchestration_service import (
    ChatOrchestrationService,
    get_chat_orchestration_service,
)
from app.services.chat_workflow_e2e_live import (
    LiveWorkflowOptions,
    WorkflowCleanupRecord,
    WorkflowStepRecord,
    cleanup_instructions,
    create_workflow_conversation,
    integration_label,
    live_orchestration_session,
    resolve_live_connected_integrations,
    run_live_cleanup,
)
from app.services.conversation_state_service import DEFAULT_TASK_STATE
from app.services.conversational_execution_service import ExecutionResult

ScenarioStatus = Literal["passed", "failed", "skipped", "blocked"]
WorkflowCheckName = Literal[
    "multi_tool_planning",
    "tool_sequencing",
    "parameter_carryover",
    "state_persistence",
    "approval_gating",
    "useful_final_response",
    "audit_events",
    "failure_recovery",
]


@dataclass(frozen=True)
class WorkflowStepExpectation:
    invoke_actions: tuple[str, ...]
    kind: Literal["read", "write"]
    requires_approval: bool


@dataclass(frozen=True)
class ChatWorkflowE2EScenario:
    id: str
    message: str
    connected_integrations: tuple[str, ...]
    expected_steps: tuple[WorkflowStepExpectation, ...]
    min_planned_steps: int = 2
    response_keywords: tuple[str, ...] = ("orchestration", "complete", "step")
    failure_drill_step_index: int = 1


CHAT_WORKFLOW_E2E_SCENARIOS: tuple[ChatWorkflowE2EScenario, ...] = (
    ChatWorkflowE2EScenario(
        id="hubspot_contacts_summarize_asana_tasks",
        message=(
            "Search HubSpot for contacts from Acme, summarize the best 5, "
            "then create follow-up tasks in Asana"
        ),
        connected_integrations=("hubspot", "asana"),
        expected_steps=(
            WorkflowStepExpectation(
                invoke_actions=("hubspot.contacts.search",),
                kind="read",
                requires_approval=False,
            ),
            WorkflowStepExpectation(
                invoke_actions=("asana.tasks.create",),
                kind="write",
                requires_approval=True,
            ),
        ),
        response_keywords=("orchestration", "step", "asana", "hubspot", "complete"),
    ),
    ChatWorkflowE2EScenario(
        id="drive_doc_summarize_slack_approval",
        message=(
            "Search Google Drive for the Q3 campaign document, summarize it, "
            "then post the summary to Slack for approval"
        ),
        connected_integrations=("google_drive", "slack"),
        expected_steps=(
            WorkflowStepExpectation(
                invoke_actions=("drive.files.list", "google_drive.files.list"),
                kind="read",
                requires_approval=False,
            ),
            WorkflowStepExpectation(
                invoke_actions=("slack.post_message",),
                kind="write",
                requires_approval=True,
            ),
        ),
        response_keywords=("slack", "orchestration", "summary", "step", "complete"),
    ),
    ChatWorkflowE2EScenario(
        id="asana_task_slack_confirmation",
        message=(
            "Create an Asana task for reviewing the Q3 campaign, "
            "then post a confirmation message to Slack"
        ),
        connected_integrations=("asana", "slack"),
        expected_steps=(
            WorkflowStepExpectation(
                invoke_actions=("asana.tasks.create",),
                kind="write",
                requires_approval=True,
            ),
            WorkflowStepExpectation(
                invoke_actions=("slack.post_message",),
                kind="write",
                requires_approval=True,
            ),
        ),
        response_keywords=("asana", "slack", "orchestration", "step", "complete"),
    ),
    ChatWorkflowE2EScenario(
        id="hubspot_stale_deals_update_approval",
        message=(
            "Search HubSpot for stale deals, identify the oldest ones, "
            "then update those deal stages after approval"
        ),
        connected_integrations=("hubspot",),
        expected_steps=(
            WorkflowStepExpectation(
                invoke_actions=(
                    "hubspot.deals.search",
                    "hubspot.deals.list",
                    "hubspot.contacts.search",
                ),
                kind="read",
                requires_approval=False,
            ),
            WorkflowStepExpectation(
                invoke_actions=("hubspot.deals.update", "hubspot.deals.update_stage"),
                kind="write",
                requires_approval=True,
            ),
        ),
        response_keywords=("hubspot", "deal", "orchestration", "step", "complete"),
    ),
    ChatWorkflowE2EScenario(
        id="sheet_rows_hubspot_contact_approval",
        message=(
            "Find a Google Sheet with lead rows, summarize the key records, "
            "then create a HubSpot contact from the top row after approval"
        ),
        connected_integrations=("google_drive", "hubspot"),
        expected_steps=(
            WorkflowStepExpectation(
                invoke_actions=("drive.files.list", "google_drive.files.list"),
                kind="read",
                requires_approval=False,
            ),
            WorkflowStepExpectation(
                invoke_actions=("hubspot.contacts.create",),
                kind="write",
                requires_approval=True,
            ),
        ),
        response_keywords=("hubspot", "sheet", "orchestration", "step", "complete"),
    ),
)


@dataclass
class WorkflowCheckResult:
    check: WorkflowCheckName
    status: ScenarioStatus
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"check": self.check, "status": self.status, "detail": self.detail}


@dataclass
class WorkflowRunResult:
    scenario_id: str
    message: str
    status: ScenarioStatus
    checks: list[WorkflowCheckResult] = field(default_factory=list)
    planned_steps: list[dict[str, Any]] = field(default_factory=list)
    executed_actions: list[str] = field(default_factory=list)
    audit_events: list[str] = field(default_factory=list)
    turn_messages: list[str] = field(default_factory=list)
    final_message: str | None = None
    conversation_id: str | None = None
    mode: Literal["dry_run", "live"] = "dry_run"
    step_records: list[WorkflowStepRecord] = field(default_factory=list)
    cleanup_records: list[WorkflowCleanupRecord] = field(default_factory=list)
    cleanup_instructions: list[str] = field(default_factory=list)
    missing_integrations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        passed = sum(1 for c in self.checks if c.status == "passed")
        failed = sum(1 for c in self.checks if c.status == "failed")
        skipped = sum(1 for c in self.checks if c.status == "skipped")
        return {
            "scenarioId": self.scenario_id,
            "message": self.message,
            "status": self.status,
            "mode": self.mode,
            "conversationId": self.conversation_id,
            "checks": [c.to_dict() for c in self.checks],
            "summary": {"passed": passed, "failed": failed, "skipped": skipped},
            "plannedSteps": self.planned_steps,
            "executedActions": self.executed_actions,
            "auditEvents": self.audit_events,
            "turnMessages": self.turn_messages,
            "finalMessage": self.final_message,
            "stepRecords": [row.to_dict() for row in self.step_records],
            "cleanupRecords": [row.to_dict() for row in self.cleanup_records],
            "cleanupInstructions": self.cleanup_instructions,
            "missingIntegrations": self.missing_integrations,
        }


def _record_check(
    results: list[WorkflowCheckResult],
    check: WorkflowCheckName,
    ok: bool,
    detail: str,
    *,
    skip: bool = False,
) -> None:
    if skip:
        results.append(WorkflowCheckResult(check=check, status="skipped", detail=detail))
    elif ok:
        results.append(WorkflowCheckResult(check=check, status="passed", detail=detail))
    else:
        results.append(WorkflowCheckResult(check=check, status="failed", detail=detail))


def _merge_task_state(current: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(current)
    for key, value in updates.items():
        if key == "clarified_params" and isinstance(value, dict):
            merged["clarified_params"] = {**(merged.get("clarified_params") or {}), **value}
        elif key == "completed_steps" and isinstance(value, list):
            merged["completed_steps"] = list(value)
        else:
            merged[key] = value
    return merged


def _default_memory_state() -> dict[str, Any]:
    state = deepcopy(DEFAULT_TASK_STATE)
    state["pending_task"] = None
    return state


def _orch_task_state(turn: dict[str, Any]) -> dict[str, Any]:
    state = dict(turn.get("task_state") or {})
    pending = turn.get("pending_task") or state.get("pending_task")
    if pending:
        state["pending_task"] = pending
        params = pending.get("params") or state.get("clarified_params") or {}
        if params:
            state["clarified_params"] = params
    return state


def _planned_invoke_actions(steps: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    for step in steps:
        plan = step.get("plan") if isinstance(step.get("plan"), dict) else {}
        action = str(plan.get("invoke_action") or "")
        if action:
            actions.append(action)
    return actions


def _step_expectation_matches(action: str, expectation: WorkflowStepExpectation) -> bool:
    return action in expectation.invoke_actions


@contextmanager
def _memory_state_patches(orchestration: ChatOrchestrationService):
    store: dict[str, dict[str, Any]] = {}

    async def get_task_state(conversation_id: str, org_id: str, *, client: Any | None = None):
        return deepcopy(store.get(conversation_id) or _default_memory_state())

    async def update_task_state(
        conversation_id: str,
        org_id: str,
        updates: dict[str, Any],
        *,
        client: Any | None = None,
    ):
        current = store.get(conversation_id) or _default_memory_state()
        store[conversation_id] = _merge_task_state(current, updates)

    orchestration._state.get_task_state = get_task_state  # type: ignore[method-assign]
    orchestration._state.update_task_state = update_task_state  # type: ignore[method-assign]
    yield store


@contextmanager
def _execution_patches(
    orchestration: ChatOrchestrationService,
    connected: list[str],
    *,
    fail_at_execute_index: int | None = None,
    audit_events: list[str],
    executed_actions: list[str],
    execute_payloads: list[dict[str, Any]],
):
    execute_counter = {"n": 0}

    async def _fake_risk(*_args, **kwargs):
        plan = _args[2] if len(_args) > 2 else None
        requires = bool(getattr(plan, "kind", "") == "write" or getattr(plan, "destructive", False))
        return {
            "requires_approval": requires,
            "can_proceed_without_approval": not requires,
            "approval_reason": "Write action" if requires else None,
        }

    async def _fake_execute_plan(*, plan, **_kwargs):
        execute_counter["n"] += 1
        idx = execute_counter["n"] - 1
        executed_actions.append(plan.invoke_action)
        execute_payloads.append(dict(plan.args))
        audit_events.append("tool.invoke.requested")
        if fail_at_execute_index is not None and idx == fail_at_execute_index:
            audit_events.append("tool.invoke.failed")
            return ExecutionResult(
                success=False,
                entity_type="connector",
                entity_id="conn-fail",
                connector_management_url="/connectors",
                integration=getattr(plan, "integration", None),
                title=plan.label,
                body=f"Simulated failure for {plan.invoke_action}",
                task_label=plan.label,
            )
        audit_events.append("tool.invoke.completed")
        return ExecutionResult(
            success=True,
            entity_type="connector",
            entity_id="conn-e2e",
            connector_management_url="/connectors/conn-e2e",
            integration=getattr(plan, "integration", None),
            title=plan.label,
            body=f"Completed {plan.invoke_action}.",
            task_label=plan.label,
        )

    with (
        patch.object(
            orchestration._connector,
            "_live_connected_integrations",
            return_value=connected,
        ),
        patch.object(orchestration._connector, "_verify_plan_executable", return_value=None),
        patch.object(orchestration._connector, "_evaluate_risk", side_effect=_fake_risk),
        patch.object(orchestration._connector, "execute_plan", side_effect=_fake_execute_plan),
        patch("app.services.notification_emitter.emit_notification"),
        patch("app.services.chat_connector_execution_service.emit_notification"),
    ):
        yield


async def _orchestration_turn_loop(
    orchestration: ChatOrchestrationService,
    *,
    scenario: ChatWorkflowE2EScenario,
    org_id: str,
    user_id: str,
    conversation_id: str,
    client: Any,
    environment_name: str,
    classification: dict[str, Any],
    connected: list[str],
    reload_state_from_db: bool = False,
    executed_actions: list[str] | None = None,
    audit_events: list[str] | None = None,
    execute_payloads: list[dict[str, Any]] | None = None,
) -> tuple[list[str], list[str], list[dict[str, Any]], list[str], dict[str, Any] | None, list[dict[str, Any]]]:
    if executed_actions is None:
        executed_actions = []
    if audit_events is None:
        audit_events = []
    if execute_payloads is None:
        execute_payloads = []
    turn_messages: list[str] = []
    last_turn: dict[str, Any] | None = None
    planned_steps: list[dict[str, Any]] = []

    async def _task_state_for_turn(turn: dict[str, Any] | None) -> dict[str, Any]:
        if reload_state_from_db and turn:
            return await orchestration._state.get_task_state(  # noqa: SLF001
                conversation_id,
                org_id,
                client=client,
            )
        return _orch_task_state(turn or {})

    turn = await orchestration.process_turn(
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        message=scenario.message,
        classification=classification,
        task_state={},
        connected_integrations=connected,
        client=client,
        environment_name=environment_name,
    )
    if turn:
        turn_messages.append(str(turn.get("message") or ""))
        last_turn = turn
        if not planned_steps:
            params = _orch_task_state(turn).get("clarified_params") or {}
            planned_steps = list(params.get("steps") or [])

    for _ in range(12):
        if not last_turn:
            break
        pending = _orch_task_state(last_turn).get("pending_task") or {}
        status = str(pending.get("status") or "")
        mode = str(last_turn.get("dialogue_mode") or "")
        message = str(last_turn.get("message") or "")

        if status == "completed" or "orchestration complete" in message.lower():
            break
        if mode == "answer" and "failed" in message.lower():
            break
        if status not in {"awaiting_plan_confirm", "awaiting_step_confirm"}:
            break

        turn = await orchestration.process_turn(
            org_id=org_id,
            user_id=user_id,
            conversation_id=conversation_id,
            message="yes",
            classification=classification,
            task_state=await _task_state_for_turn(last_turn),
            connected_integrations=connected,
            client=client,
            environment_name=environment_name,
        )
        if not turn:
            break
        turn_messages.append(str(turn.get("message") or ""))
        last_turn = turn

    return executed_actions, audit_events, execute_payloads, turn_messages, last_turn, planned_steps


async def _drive_orchestration_to_completion(
    orchestration: ChatOrchestrationService,
    *,
    scenario: ChatWorkflowE2EScenario,
    org_id: str,
    user_id: str,
    conversation_id: str,
    client: Any,
    environment_name: str,
    classification: dict[str, Any],
    connected: list[str],
    fail_at_execute_index: int | None = None,
    live_options: LiveWorkflowOptions | None = None,
    run_id: str | None = None,
    step_records: list[WorkflowStepRecord] | None = None,
    cleanup_records: list[WorkflowCleanupRecord] | None = None,
) -> tuple[list[str], list[str], list[dict[str, Any]], list[str], dict[str, Any] | None, list[dict[str, Any]]]:
    audit_events: list[str] = []
    executed_actions: list[str] = []
    execute_payloads: list[dict[str, Any]] = []
    records = step_records if step_records is not None else []
    cleanups = cleanup_records if cleanup_records is not None else []

    if live_options is not None and run_id:
        async with live_orchestration_session(
            orchestration,
            client=client,
            org_id=org_id,
            user_id=user_id,
            environment_name=environment_name,
            connected=connected,
            options=live_options,
            run_id=run_id,
            step_records=records,
            cleanup_records=cleanups,
            executed_actions=executed_actions,
            audit_events=audit_events,
        ):
            return await _orchestration_turn_loop(
                orchestration,
                scenario=scenario,
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                client=client,
                environment_name=environment_name,
                classification=classification,
                connected=connected,
                reload_state_from_db=True,
                executed_actions=executed_actions,
                audit_events=audit_events,
                execute_payloads=execute_payloads,
            )

    with _memory_state_patches(orchestration), _execution_patches(
        orchestration,
        connected,
        fail_at_execute_index=fail_at_execute_index,
        audit_events=audit_events,
        executed_actions=executed_actions,
        execute_payloads=execute_payloads,
    ):
        return await _orchestration_turn_loop(
            orchestration,
            scenario=scenario,
            org_id=org_id,
            user_id=user_id,
            conversation_id=conversation_id,
            client=client,
            environment_name=environment_name,
            classification=classification,
            connected=connected,
            executed_actions=executed_actions,
            audit_events=audit_events,
            execute_payloads=execute_payloads,
        )


async def run_chat_workflow_e2e_scenario(
    scenario: ChatWorkflowE2EScenario,
    *,
    org_id: str,
    user_id: str,
    client: Any,
    settings: Any,
    environment_name: str = "production",
    live_execute: bool = False,
    live_options: LiveWorkflowOptions | None = None,
    include_failure_drill: bool = True,
    run_id: str | None = None,
) -> WorkflowRunResult:
    """Run one multi-step workflow scenario with validation checks."""
    checks: list[WorkflowCheckResult] = []
    run_tag = run_id or str(uuid.uuid4())
    conv_id = f"chat-workflow-{scenario.id}-{uuid.uuid4().hex[:8]}"
    orchestration = get_chat_orchestration_service(settings)
    classification = {
        "intent": "workflow_execution",
        "risk_level": "high",
        "requires_approval": True,
    }
    options = live_options or LiveWorkflowOptions()
    step_records: list[WorkflowStepRecord] = []
    cleanup_records: list[WorkflowCleanupRecord] = []
    missing_integrations: list[str] = []

    if live_execute:
        connected, missing_integrations = resolve_live_connected_integrations(
            orchestration._connector,
            client=client,
            org_id=org_id,
            scenario_integrations=scenario.connected_integrations,
            environment_name=environment_name,
        )
        if missing_integrations:
            detail = ", ".join(integration_label(v) for v in missing_integrations)
            _record_check(
                checks,
                "multi_tool_planning",
                False,
                f"Missing OAuth connectors: {detail}",
            )
            return WorkflowRunResult(
                scenario_id=scenario.id,
                message=scenario.message,
                status="blocked",
                checks=checks,
                mode="live",
                missing_integrations=missing_integrations,
            )
        conv_id = create_workflow_conversation(
            client,
            org_id=org_id,
            user_id=user_id,
            scenario_id=scenario.id,
            run_id=run_tag,
        )
        include_failure_drill = False
    else:
        connected = list(scenario.connected_integrations)

    intent_ok = orchestration.is_orchestration_intent(scenario.message, {}, connected)
    _record_check(
        checks,
        "multi_tool_planning",
        intent_ok,
        "Orchestration intent detected" if intent_ok else "Message not recognized as multi-step orchestration",
    )

    if not intent_ok:
        return WorkflowRunResult(
            scenario_id=scenario.id,
            message=scenario.message,
            status="failed",
            checks=checks,
            mode="live" if live_execute else "dry_run",
            conversation_id=conv_id if live_execute else None,
        )

    executed, audit, payloads, messages, last_turn, planned_steps = await _drive_orchestration_to_completion(
        orchestration,
        scenario=scenario,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conv_id,
        client=client,
        environment_name=environment_name,
        classification=classification,
        connected=connected,
        live_options=options if live_execute else None,
        run_id=run_tag if live_execute else None,
        step_records=step_records if live_execute else None,
        cleanup_records=cleanup_records if live_execute else None,
    )

    if live_execute and cleanup_records:
        cleanup_records = await run_live_cleanup(
            client=client,
            org_id=org_id,
            user_id=user_id,
            environment_name=environment_name,
            options=options,
            records=cleanup_records,
        )

    planned_actions = _planned_invoke_actions(planned_steps)
    plan_ok = len(planned_steps) >= scenario.min_planned_steps
    _record_check(
        checks,
        "multi_tool_planning",
        plan_ok and intent_ok,
        f"Planned {len(planned_steps)} steps: {', '.join(planned_actions) or 'none'}",
    )

    sequencing_ok = len(executed) >= 1
    sequencing_detail = f"Executed sequence: {', '.join(executed) or 'none'}"
    if sequencing_ok and scenario.expected_steps:
        for idx, expected in enumerate(scenario.expected_steps):
            if idx >= len(executed):
                sequencing_ok = False
                sequencing_detail = f"Missing execution for step {idx + 1}"
                break
            if not _step_expectation_matches(executed[idx], expected):
                sequencing_ok = False
                sequencing_detail = (
                    f"Step {idx + 1}: expected one of {expected.invoke_actions}, got {executed[idx]}"
                )
                break
    _record_check(checks, "tool_sequencing", sequencing_ok, sequencing_detail)

    carryover_ok = True
    carryover_detail = "No cross-step payload enrichment required"
    if len(executed) >= 2 and executed[-1] == "slack.post_message":
        slack_record: WorkflowStepRecord | None = None
        message_text = ""
        if live_execute and step_records:
            slack_record = next(
                (row for row in reversed(step_records) if row.invoke_action == "slack.post_message"),
                None,
            )
            message_text = str((slack_record.request_payload if slack_record else {}).get("message") or "")
        elif payloads:
            message_text = str(payloads[-1].get("message") or "")
        if slack_record and slack_record.status == "skipped":
            carryover_detail = "Slack write skipped in live read-only mode"
        elif "Orchestration summary" in message_text or "Gravitre Workflow E2E" in message_text:
            carryover_detail = "Slack message includes prior step summaries"
        elif live_execute and not options.enable_writes:
            carryover_detail = "Slack write skipped (--enable-writes)"
        else:
            carryover_ok = False
            carryover_detail = "Slack step missing orchestration summary carryover"
    _record_check(checks, "parameter_carryover", carryover_ok, carryover_detail)

    if live_execute:
        db_state = await orchestration._state.get_task_state(conv_id, org_id, client=client)  # noqa: SLF001
        persistence_ok = bool(db_state.get("pending_task") or db_state.get("clarified_params"))
        persistence_ok = persistence_ok and any(
            "orchestration" in msg.lower() or "step" in msg.lower() for msg in messages
        )
    else:
        persistence_ok = any("step" in msg.lower() and "approval" in msg.lower() for msg in messages)
        persistence_ok = persistence_ok or any(
            "orchestration" in msg.lower() and "yes" in msg.lower() for msg in messages
        )
    _record_check(
        checks,
        "state_persistence",
        persistence_ok,
        "Observed plan/step confirm prompts across turns" if persistence_ok else "Missing confirm turns",
    )

    approval_ok = any("approval" in msg.lower() or "yes" in msg.lower() for msg in messages)
    write_expected = any(step.requires_approval for step in scenario.expected_steps)
    if write_expected:
        _record_check(
            checks,
            "approval_gating",
            approval_ok,
            "Write steps paused for approval" if approval_ok else "No approval prompt for write steps",
        )
    else:
        _record_check(checks, "approval_gating", True, "No write steps in scenario")

    final_message = messages[-1] if messages else None
    response_ok = bool(final_message) and any(
        word in final_message.lower() for word in scenario.response_keywords
    )
    _record_check(
        checks,
        "useful_final_response",
        response_ok,
        (final_message or "")[:240],
    )

    invoke_completed = audit.count("tool.invoke.completed")
    if live_execute:
        audit_ok = invoke_completed >= 1 and all(
            row.audit_event_ids or row.status in {"skipped", "blocked"}
            for row in step_records
            if row.status != "failed"
        )
        audit_detail = (
            f"{invoke_completed} completed tool audits; "
            f"{sum(len(r.audit_event_ids) for r in step_records)} audit event ids captured"
        )
    else:
        audit_ok = invoke_completed == len(executed) and invoke_completed >= 1
        audit_detail = f"{invoke_completed} completed audit events for {len(executed)} tool calls"
    _record_check(checks, "audit_events", audit_ok, audit_detail)

    if include_failure_drill and not live_execute:
        fail_executed, fail_audit, _, fail_messages, fail_turn, _ = await _drive_orchestration_to_completion(
            orchestration,
            scenario=scenario,
            org_id=org_id,
            user_id=user_id,
            conversation_id=f"{conv_id}-fail",
            client=client,
            environment_name=environment_name,
            classification=classification,
            connected=connected,
            fail_at_execute_index=scenario.failure_drill_step_index,
        )
        fail_msg = str((fail_turn or {}).get("message") or (fail_messages[-1] if fail_messages else ""))
        completed_before_fail = fail_audit.count("tool.invoke.completed")
        recovery_ok = (
            "failed" in fail_msg.lower()
            and len(fail_executed) >= scenario.failure_drill_step_index + 1
            and completed_before_fail == scenario.failure_drill_step_index
            and fail_audit.count("tool.invoke.failed") >= 1
        )
        _record_check(
            checks,
            "failure_recovery",
            recovery_ok,
            fail_msg[:240] if fail_msg else "No failure turn captured",
        )
    else:
        _record_check(
            checks,
            "failure_recovery",
            True,
            "Failure drill skipped in live mode" if live_execute else "Failure drill skipped",
            skip=True,
        )

    failed = any(c.status == "failed" for c in checks)
    instructions = cleanup_instructions(cleanup_records)
    return WorkflowRunResult(
        scenario_id=scenario.id,
        message=scenario.message,
        status="failed" if failed else "passed",
        checks=checks,
        planned_steps=planned_steps,
        executed_actions=executed,
        audit_events=audit,
        turn_messages=messages,
        final_message=final_message,
        conversation_id=conv_id if live_execute else None,
        mode="live" if live_execute else "dry_run",
        step_records=step_records,
        cleanup_records=cleanup_records,
        cleanup_instructions=instructions,
        missing_integrations=missing_integrations,
    )


async def run_all_chat_workflow_e2e_scenarios(
    *,
    org_id: str,
    user_id: str,
    client: Any,
    settings: Any,
    environment_name: str = "production",
    live_execute: bool = False,
    live_options: LiveWorkflowOptions | None = None,
    scenario_ids: list[str] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    selected = [s for s in CHAT_WORKFLOW_E2E_SCENARIOS if not scenario_ids or s.id in scenario_ids]
    batch_run_id = run_id or str(uuid.uuid4())
    options = live_options or LiveWorkflowOptions()
    results = [
        await run_chat_workflow_e2e_scenario(
            scenario,
            org_id=org_id,
            user_id=user_id,
            client=client,
            settings=settings,
            environment_name=environment_name,
            live_execute=live_execute,
            live_options=options,
            run_id=batch_run_id,
        )
        for scenario in selected
    ]
    summary = {"passed": 0, "failed": 0, "skipped": 0, "blocked": 0}
    for row in results:
        summary[row.status] = summary.get(row.status, 0) + 1
    return {
        "runId": batch_run_id,
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "orgId": org_id,
        "environment": environment_name,
        "liveExecute": live_execute,
        "enableWrites": options.enable_writes,
        "allowDestructive": options.allow_destructive,
        "autoCleanup": options.auto_cleanup,
        "summary": summary,
        "scenarios": [row.to_dict() for row in results],
    }


def export_workflow_e2e_json(path: str | Any, report: dict[str, Any]) -> Any:
    from pathlib import Path

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return out


def export_workflow_e2e_csv(path: str | Any, report: dict[str, Any]) -> Any:
    from pathlib import Path

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for scenario in report.get("scenarios") or []:
        step_records = scenario.get("stepRecords") or []
        if step_records:
            for step in step_records:
                rows.append(
                    {
                        "scenarioId": scenario.get("scenarioId"),
                        "scenarioStatus": scenario.get("status"),
                        "mode": scenario.get("mode"),
                        "stepId": step.get("stepId"),
                        "invokeAction": step.get("invokeAction"),
                        "stepStatus": step.get("status"),
                        "failureReason": step.get("failureReason"),
                        "auditEventIds": "|".join(step.get("auditEventIds") or []),
                        "responseShape": json.dumps(step.get("responseShape") or {}),
                        "requestPayload": json.dumps(step.get("requestPayload") or {}),
                    }
                )
        for check in scenario.get("checks") or []:
            rows.append(
                {
                    "scenarioId": scenario.get("scenarioId"),
                    "scenarioStatus": scenario.get("status"),
                    "mode": scenario.get("mode"),
                    "stepId": "",
                    "invokeAction": "",
                    "stepStatus": "",
                    "failureReason": check.get("detail"),
                    "auditEventIds": "",
                    "responseShape": "",
                    "requestPayload": check.get("check"),
                }
            )
    fieldnames = [
        "scenarioId",
        "scenarioStatus",
        "mode",
        "stepId",
        "invokeAction",
        "stepStatus",
        "failureReason",
        "auditEventIds",
        "responseShape",
        "requestPayload",
    ]
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return out
