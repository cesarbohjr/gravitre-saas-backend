"""End-to-end AI Chat scenarios using real connected apps."""
from __future__ import annotations

import csv
import json
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal
from unittest.mock import patch

from app.services.chat_connector_execution_service import (
    ChatConnectorExecutionService,
    get_chat_connector_execution_service,
)
from app.services.chat_connector_models import ConnectorActionPlan

ScenarioStatus = Literal["passed", "failed", "skipped", "blocked"]
CheckName = Literal[
    "intent_detection",
    "tool_selection",
    "parameter_filling",
    "approval_gating",
    "successful_execution",
    "useful_final_response",
    "audit_log_created",
]
ParamChecker = Callable[[dict[str, Any]], str | None]


def _contains_keys(*keys: str) -> ParamChecker:
    def _check(args: dict[str, Any]) -> str | None:
        for key in keys:
            if key not in args or args[key] in (None, "", {}):
                return f"Missing or empty parameter: {key}"
        return None

    return _check


def _query_contains(token: str) -> ParamChecker:
    def _check(args: dict[str, Any]) -> str | None:
        query = str(args.get("query") or "")
        if token.lower() not in query.lower():
            return f"Expected query to contain {token!r}, got {query!r}"
        return None

    return _check


def _properties_has(key: str) -> ParamChecker:
    def _check(args: dict[str, Any]) -> str | None:
        props = args.get("properties")
        if not isinstance(props, dict) or not props.get(key):
            return f"Expected properties.{key}"
        return None

    return _check


@dataclass(frozen=True)
class ChatE2EScenario:
    id: str
    message: str
    connected_integrations: tuple[str, ...]
    expected_intent: str
    expected_invoke_actions: tuple[str, ...]
    expected_kind: Literal["read", "write"]
    requires_approval: bool
    param_checkers: tuple[ParamChecker, ...] = ()
    confirmation_message: str = "yes"
    response_keywords: tuple[str, ...] = ()
    follow_up_read_action: str | None = None
    follow_up_env_key: str | None = None


CHAT_E2E_SCENARIOS: tuple[ChatE2EScenario, ...] = (
    ChatE2EScenario(
        id="hubspot_search_acme_contacts",
        message="Search HubSpot for contacts from Acme.",
        connected_integrations=("hubspot",),
        expected_intent="crm_lookup",
        expected_invoke_actions=("hubspot.contacts.search",),
        expected_kind="read",
        requires_approval=False,
        param_checkers=(_contains_keys("query"), _query_contains("Acme")),
        response_keywords=("contact", "hubspot", "done", "found", "search"),
    ),
    ChatE2EScenario(
        id="asana_create_q3_review_task",
        message=(
            "Create a task in Asana in the Marketing project for reviewing the Q3 campaign by Friday."
        ),
        connected_integrations=("asana",),
        expected_intent="workflow_execution",
        expected_invoke_actions=("asana.tasks.create",),
        expected_kind="write",
        requires_approval=True,
        param_checkers=(_contains_keys("name"),),
        response_keywords=("asana", "task", "yes", "approval", "confirm"),
    ),
    ChatE2EScenario(
        id="slack_post_summary_for_approval",
        message="Post this summary to Slack for approval.",
        connected_integrations=("slack",),
        expected_intent="workflow_execution",
        expected_invoke_actions=("slack.post_message",),
        expected_kind="write",
        requires_approval=True,
        param_checkers=(_contains_keys("channel", "message"),),
        response_keywords=("slack", "yes", "approval", "confirm", "post"),
    ),
    ChatE2EScenario(
        id="google_sheet_find_and_summarize",
        message="Find a Google Sheet and summarize the rows.",
        connected_integrations=("google_drive",),
        expected_intent="data_lookup",
        expected_invoke_actions=("google_drive.files.list", "drive.files.list"),
        expected_kind="read",
        requires_approval=False,
        param_checkers=(_contains_keys("query"),),
        response_keywords=("sheet", "file", "found", "rows", "done", "spreadsheet"),
        follow_up_read_action="sheets.values.get",
        follow_up_env_key="CHAT_E2E_GOOGLE_SHEETS_ID",
    ),
    ChatE2EScenario(
        id="hubspot_deal_create_with_approval",
        message="Create a HubSpot deal and ask for approval before saving.",
        connected_integrations=("hubspot",),
        expected_intent="workflow_execution",
        expected_invoke_actions=("hubspot.deals.create",),
        expected_kind="write",
        requires_approval=True,
        param_checkers=(_properties_has("dealname"),),
        response_keywords=("deal", "hubspot", "yes", "approval", "confirm", "saving"),
    ),
)


@dataclass
class ScenarioCheckResult:
    check: CheckName
    status: ScenarioStatus
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"check": self.check, "status": self.status, "detail": self.detail}


@dataclass
class ScenarioRunResult:
    scenario_id: str
    message: str
    status: ScenarioStatus
    checks: list[ScenarioCheckResult] = field(default_factory=list)
    plan: dict[str, Any] | None = None
    turn_message: str | None = None
    execution_success: bool | None = None
    audit_events: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        passed = sum(1 for c in self.checks if c.status == "passed")
        failed = sum(1 for c in self.checks if c.status == "failed")
        skipped = sum(1 for c in self.checks if c.status == "skipped")
        return {
            "scenarioId": self.scenario_id,
            "message": self.message,
            "status": self.status,
            "checks": [c.to_dict() for c in self.checks],
            "summary": {"passed": passed, "failed": failed, "skipped": skipped},
            "plan": self.plan,
            "turnMessage": self.turn_message,
            "executionSuccess": self.execution_success,
            "auditEvents": self.audit_events,
        }


def infer_chat_classification(message: str, *, requires_approval: bool) -> dict[str, Any]:
    lowered = message.lower()
    if "hubspot" in lowered and any(v in lowered for v in ("search", "find", "lookup")):
        intent = "crm_lookup"
    elif "sheet" in lowered or "summarize" in lowered:
        intent = "data_lookup"
    else:
        intent = "workflow_execution"
    return {
        "intent": intent,
        "risk_level": "high" if requires_approval else "low",
        "requires_approval": requires_approval,
    }


def _record_check(
    results: list[ScenarioCheckResult],
    check: CheckName,
    ok: bool,
    detail: str,
    *,
    skip: bool = False,
) -> None:
    if skip:
        results.append(ScenarioCheckResult(check=check, status="skipped", detail=detail))
    elif ok:
        results.append(ScenarioCheckResult(check=check, status="passed", detail=detail))
    else:
        results.append(ScenarioCheckResult(check=check, status="failed", detail=detail))


def _plan_to_dict(plan: ConnectorActionPlan | None) -> dict[str, Any] | None:
    if not plan:
        return None
    return {
        "toolName": plan.tool_name,
        "invokeAction": plan.invoke_action,
        "integration": plan.integration,
        "kind": plan.kind,
        "label": plan.label,
        "args": plan.args,
        "requiresApproval": plan.requires_approval,
    }


@contextmanager
def _dry_run_patches(service: ChatConnectorExecutionService, connected: list[str]):
    async def _fake_execute_tool(*, ctx, tool_name, args=None):
        from app.services.tool_service import write_audit_event

        write_audit_event(
            ctx.client,
            ctx.org_id,
            ctx.actor_id,
            action="tool.invoke.requested",
            resource_type="conversation",
            resource_id=tool_name,
            metadata={"action": tool_name, "dry_run": True},
        )
        write_audit_event(
            ctx.client,
            ctx.org_id,
            ctx.actor_id,
            action="tool.invoke.completed",
            resource_type="conversation",
            resource_id=tool_name,
            metadata={"success": True, "dry_run": True},
        )
        return {
            "success": True,
            "tool": tool_name,
            "action": tool_name,
            "result": {"dry_run": True},
            "connector_id": "conn-e2e",
        }

    async def _fake_risk(*_args, **kwargs):
        plan = _args[2] if len(_args) > 2 else None
        requires = bool(getattr(plan, "kind", "") == "write" or getattr(plan, "destructive", False))
        return {
            "requires_approval": requires,
            "can_proceed_without_approval": not requires,
            "approval_reason": "Write action" if requires else None,
        }

    with (
        patch.object(service, "_live_connected_integrations", return_value=connected),
        patch.object(service, "_verify_plan_executable", return_value=None),
        patch.object(service, "_evaluate_risk", side_effect=_fake_risk),
        patch.object(service._registry, "execute_tool", side_effect=_fake_execute_tool),
        patch("app.services.chat_connector_execution_service.emit_notification"),
    ):
        yield


@contextmanager
def _live_patches(service: ChatConnectorExecutionService, connected: list[str]):
    async def _fake_risk(*_args, **kwargs):
        plan = _args[2] if len(_args) > 2 else None
        requires = bool(getattr(plan, "kind", "") == "write" or getattr(plan, "destructive", False))
        return {
            "requires_approval": requires,
            "can_proceed_without_approval": not requires,
            "approval_reason": "Write action" if requires else None,
        }

    with (
        patch.object(service, "_live_connected_integrations", return_value=connected),
        patch.object(service, "_verify_plan_executable", return_value=None),
        patch.object(service, "_evaluate_risk", side_effect=_fake_risk),
        patch("app.services.chat_connector_execution_service.emit_notification"),
    ):
        yield


@contextmanager
def _audit_capture():
    events: list[str] = []

    def _capture(_client, _org, _actor, *, action, **_kwargs):
        events.append(str(action))

    with patch("app.services.tool_service.write_audit_event", side_effect=_capture):
        yield events


def _confirm_task_state(pre_turn: dict[str, Any]) -> dict[str, Any]:
    state = dict(pre_turn.get("task_state") or {})
    pending = pre_turn.get("pending_task") or state.get("pending_task")
    if pending:
        state["pending_task"] = pending
        if not state["pending_task"].get("status"):
            state["pending_task"] = {**state["pending_task"], "status": "awaiting_confirm"}
        params = pending.get("params") or state.get("clarified_params") or {}
        if params:
            state["clarified_params"] = params
    return state


async def run_chat_e2e_scenario(
    scenario: ChatE2EScenario,
    *,
    org_id: str,
    user_id: str,
    client: Any,
    settings: Any,
    environment_name: str = "production",
    live_execute: bool = False,
    env: dict[str, str] | None = None,
    conversation_id: str | None = None,
) -> ScenarioRunResult:
    """Run one chat E2E scenario through planning, approval, and optional live execution."""
    env_map = dict(env or {})
    conv_id = conversation_id or f"chat-e2e-{scenario.id}-{uuid.uuid4().hex[:8]}"
    service = get_chat_connector_execution_service(settings)
    checks: list[ScenarioCheckResult] = []
    audit_events: list[str] = []
    connected = list(scenario.connected_integrations)

    intent_ok = service.is_connector_intent(scenario.message, {})
    classification = infer_chat_classification(
        scenario.message,
        requires_approval=scenario.requires_approval,
    )
    intent_detail = "Connector intent detected"
    if not intent_ok:
        intent_detail = "Message not recognized as connector intent"
    elif classification["intent"] != scenario.expected_intent:
        intent_ok = False
        intent_detail = f"Expected intent {scenario.expected_intent}, inferred {classification['intent']}"
    _record_check(checks, "intent_detection", intent_ok, intent_detail)

    plan = service.plan_action(
        scenario.message,
        connected_integrations=connected,
        task_state={},
    )
    tool_ok = bool(
        plan
        and plan.invoke_action in scenario.expected_invoke_actions
        and plan.kind == scenario.expected_kind
    )
    _record_check(
        checks,
        "tool_selection",
        tool_ok,
        (
            f"Selected {plan.invoke_action} ({plan.tool_name})"
            if plan and tool_ok
            else f"Expected one of {scenario.expected_invoke_actions}, got {getattr(plan, 'invoke_action', None)}"
        ),
    )

    param_ok = True
    param_detail: list[str] = []
    if plan and plan.args:
        for checker in scenario.param_checkers:
            err = checker(plan.args)
            if err:
                param_ok = False
                param_detail.append(err)
    elif scenario.param_checkers:
        param_ok = False
        param_detail.append("No parameters extracted")
    _record_check(
        checks,
        "parameter_filling",
        param_ok,
        "; ".join(param_detail) if param_detail else "Parameters look valid",
    )

    turn_message: str | None = None
    execution_success: bool | None = None

    if not plan:
        _record_check(checks, "approval_gating", False, "No plan to evaluate approval")
        _record_check(checks, "successful_execution", False, "Skipped — no plan", skip=not live_execute)
        _record_check(checks, "useful_final_response", False, "Skipped — no plan", skip=True)
        _record_check(checks, "audit_log_created", False, "Skipped — no plan", skip=not live_execute)
        return ScenarioRunResult(
            scenario_id=scenario.id,
            message=scenario.message,
            status="failed",
            checks=checks,
            plan=_plan_to_dict(plan),
        )

    patch_ctx = _live_patches(service, connected) if live_execute else _dry_run_patches(service, connected)
    with patch_ctx:
        if scenario.requires_approval:
            pre_turn = await service.process_turn(
                org_id=org_id,
                user_id=user_id,
                conversation_id=conv_id,
                message=scenario.message,
                classification=classification,
                task_state={},
                connected_integrations=connected,
                client=client,
                environment_name=environment_name,
            )
            approval_ok = bool(pre_turn and pre_turn.get("dialogue_mode") == "confirm")
            _record_check(
                checks,
                "approval_gating",
                approval_ok,
                (pre_turn or {}).get("message", "")[:240] if pre_turn else "No confirm turn returned",
            )
            turn_message = (pre_turn or {}).get("message")

            if live_execute and approval_ok:
                with _audit_capture() as captured:
                    confirm_turn = await service.process_turn(
                        org_id=org_id,
                        user_id=user_id,
                        conversation_id=conv_id,
                        message=scenario.confirmation_message,
                        classification=classification,
                        task_state=_confirm_task_state(pre_turn),
                        connected_integrations=connected,
                        client=client,
                        environment_name=environment_name,
                    )
                audit_events = captured
                execution_success = bool((confirm_turn or {}).get("execution_result", {}).get("success"))
                turn_message = (confirm_turn or {}).get("message") or turn_message
            elif not live_execute and approval_ok:
                with _audit_capture() as captured:
                    confirm_turn = await service.process_turn(
                        org_id=org_id,
                        user_id=user_id,
                        conversation_id=conv_id,
                        message=scenario.confirmation_message,
                        classification=classification,
                        task_state=_confirm_task_state(pre_turn),
                        connected_integrations=connected,
                        client=client,
                        environment_name=environment_name,
                    )
                audit_events = [a for a in captured if a.startswith("tool.invoke.")]
                execution_success = bool((confirm_turn or {}).get("execution_result", {}).get("success"))
                turn_message = (confirm_turn or {}).get("message") or turn_message
                _record_check(
                    checks,
                    "successful_execution",
                    execution_success is True,
                    "Confirmed write executed (mocked)",
                )
                _record_check(
                    checks,
                    "audit_log_created",
                    bool(audit_events),
                    ", ".join(audit_events) if audit_events else "No tool.invoke audit captured on confirm",
                )
        else:
            _record_check(checks, "approval_gating", True, "Read action — no approval required")
            if live_execute:
                with _audit_capture() as captured:
                    read_turn = await service.process_turn(
                        org_id=org_id,
                        user_id=user_id,
                        conversation_id=conv_id,
                        message=scenario.message,
                        classification=classification,
                        task_state={},
                        connected_integrations=connected,
                        client=client,
                        environment_name=environment_name,
                    )
                audit_events = captured
                execution_success = bool((read_turn or {}).get("execution_result", {}).get("success"))
                turn_message = (read_turn or {}).get("message")

                if execution_success and scenario.follow_up_read_action and scenario.follow_up_env_key:
                    sheet_id = env_map.get(scenario.follow_up_env_key, "").strip()
                    if sheet_id:
                        follow_plan = ConnectorActionPlan(
                            tool_name="sheets_values_get",
                            invoke_action=scenario.follow_up_read_action,
                            integration="google_sheets",
                            kind="read",
                            label="Read sheet rows",
                            args={
                                "spreadsheet_id": sheet_id,
                                "range": env_map.get("CHAT_E2E_GOOGLE_SHEETS_RANGE", "Sheet1!A1:Z50"),
                            },
                        )
                        with _audit_capture() as follow_captured:
                            await service.execute_plan(
                                org_id=org_id,
                                user_id=user_id,
                                conversation_id=conv_id,
                                plan=follow_plan,
                                client=client,
                                classification=classification,
                                environment_name=environment_name,
                            )
                        audit_events.extend(follow_captured)

                _record_check(
                    checks,
                    "successful_execution",
                    execution_success is True,
                    "Live read executed" if execution_success else "Live read failed",
                )
                _record_check(
                    checks,
                    "audit_log_created",
                    any(a.startswith("tool.invoke.") for a in audit_events),
                    ", ".join(audit_events) if audit_events else "No tool.invoke audit events",
                )
            else:
                with _audit_capture() as captured:
                    read_turn = await service.process_turn(
                        org_id=org_id,
                        user_id=user_id,
                        conversation_id=conv_id,
                        message=scenario.message,
                        classification=classification,
                        task_state={},
                        connected_integrations=connected,
                        client=client,
                        environment_name=environment_name,
                    )
                audit_events = [a for a in captured if a.startswith("tool.invoke.")]
                execution_success = bool((read_turn or {}).get("execution_result", {}).get("success"))
                turn_message = (read_turn or {}).get("message")
                _record_check(checks, "successful_execution", execution_success is True, "Read executed (mocked)")
                _record_check(
                    checks,
                    "audit_log_created",
                    bool(audit_events),
                    ", ".join(audit_events) if audit_events else "No tool.invoke audit captured",
                )

    if live_execute and scenario.requires_approval and not any(c.check == "successful_execution" for c in checks):
        _record_check(
            checks,
            "successful_execution",
            execution_success is True,
            "Live write executed" if execution_success else "Live write failed",
        )
        _record_check(
            checks,
            "audit_log_created",
            any(a.startswith("tool.invoke.") for a in audit_events),
            ", ".join(audit_events) if audit_events else "No tool.invoke audit events",
        )

    response_ok = True
    if turn_message and scenario.response_keywords:
        lowered = turn_message.lower()
        response_ok = any(word in lowered for word in scenario.response_keywords)
    elif scenario.requires_approval and not turn_message:
        response_ok = False
    _record_check(
        checks,
        "useful_final_response",
        response_ok,
        (turn_message or "")[:240] if turn_message else "No assistant turn text",
    )

    failed = any(c.status == "failed" for c in checks)
    status: ScenarioStatus = "failed" if failed else "passed"
    return ScenarioRunResult(
        scenario_id=scenario.id,
        message=scenario.message,
        status=status,
        checks=checks,
        plan=_plan_to_dict(plan),
        turn_message=turn_message,
        execution_success=execution_success,
        audit_events=audit_events,
    )


async def run_all_chat_e2e_scenarios(
    *,
    org_id: str,
    user_id: str,
    client: Any,
    settings: Any,
    environment_name: str = "production",
    live_execute: bool = False,
    env: dict[str, str] | None = None,
    scenario_ids: list[str] | None = None,
) -> dict[str, Any]:
    selected = [s for s in CHAT_E2E_SCENARIOS if not scenario_ids or s.id in scenario_ids]
    results = [
        await run_chat_e2e_scenario(
            scenario,
            org_id=org_id,
            user_id=user_id,
            client=client,
            settings=settings,
            environment_name=environment_name,
            live_execute=live_execute,
            env=env,
        )
        for scenario in selected
    ]
    summary = {"passed": 0, "failed": 0, "skipped": 0}
    for row in results:
        summary[row.status] = summary.get(row.status, 0) + 1
    return {
        "runId": str(uuid.uuid4()),
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "orgId": org_id,
        "environment": environment_name,
        "liveExecute": live_execute,
        "summary": summary,
        "scenarios": [row.to_dict() for row in results],
    }


def export_chat_e2e_json(path: str | Any, report: dict[str, Any]) -> Any:
    from pathlib import Path

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return out


def export_chat_e2e_csv(path: str | Any, report: dict[str, Any]) -> Any:
    from pathlib import Path

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for scenario in report.get("scenarios") or []:
        for check in scenario.get("checks") or []:
            rows.append(
                {
                    "scenarioId": scenario.get("scenarioId"),
                    "message": scenario.get("message"),
                    "scenarioStatus": scenario.get("status"),
                    "check": check.get("check"),
                    "checkStatus": check.get("status"),
                    "detail": check.get("detail"),
                    "invokeAction": (scenario.get("plan") or {}).get("invokeAction"),
                }
            )
    fieldnames = list(rows[0].keys()) if rows else [
        "scenarioId",
        "message",
        "scenarioStatus",
        "check",
        "checkStatus",
        "detail",
        "invokeAction",
    ]
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return out
