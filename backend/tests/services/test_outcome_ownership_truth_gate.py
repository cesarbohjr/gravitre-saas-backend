"""Outcome Ownership: one evidence vocabulary decides every completion claim."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.outcome_verification import (
    evidence_is_verified,
    outcome_from_tool_calls,
    rollup,
    verify_write_now,
)


# ---------------------------------------------------------------------------
# Evidence reader
# ---------------------------------------------------------------------------


def test_bare_verified_flag_is_not_evidence() -> None:
    assert evidence_is_verified({"verified": True}) is False
    assert evidence_is_verified({"verification": {"verified": True}}) is False


def test_attributable_evidence_is_accepted() -> None:
    assert evidence_is_verified({"verification": {"verified": True, "method": "entity_get"}})
    assert evidence_is_verified({"verified": True, "read_action": "hubspot.contacts.get"})


def test_send_receipt_counts_as_proof_but_webhook_2xx_does_not() -> None:
    sent = verify_write_now(invoke_action="slack.post_message", result_data={"ok": True, "ts": "1.2"})
    assert sent.verified and sent.method == "provider_receipt"
    hook = verify_write_now(invoke_action="webhook.post", result_data={"status": 200, "id": "x"})
    assert hook.verified is False


# ---------------------------------------------------------------------------
# Rollup
# ---------------------------------------------------------------------------


def _w(success: bool = True, verified: bool | None = None, **extra: Any) -> dict[str, Any]:
    child: dict[str, Any] = {"consequential": True, "success": success, **extra}
    if verified is not None:
        child["verification"] = {"verified": verified, "method": "entity_get"}
    return child


@pytest.mark.parametrize(
    ("children", "status"),
    [
        ([_w(verified=True), _w(verified=True)], "completed"),
        ([_w(verified=True), _w()], "verification_inconclusive"),
        ([_w(verified=True), _w(success=False)], "partial_success"),
        ([_w(success=False)], "failed"),
        ([_w(success=False, outcome_uncertain=True)], "verification_inconclusive"),
        ([{"consequential": False, "success": True}], "completed"),
    ],
)
def test_rollup_status(children: list[dict[str, Any]], status: str) -> None:
    assert rollup(children).status == status


def test_agent_outcome_ignores_recovered_read_failures() -> None:
    calls = [
        {"tool": "search", "result": {"success": False, "action": "hubspot.contacts.search"}},
        {"tool": "search", "result": {"success": True, "action": "hubspot.contacts.search"}},
    ]
    assert outcome_from_tool_calls(calls).status == "completed"


def test_agent_outcome_requires_write_proof() -> None:
    unproven = [{"tool": "post", "result": {"success": True, "action": "slack.post_message"}}]
    assert outcome_from_tool_calls(unproven).status == "verification_inconclusive"
    proven = [
        {
            "tool": "post",
            "result": {
                "success": True,
                "action": "slack.post_message",
                "verification": {"verified": True, "method": "provider_receipt"},
            },
        }
    ]
    assert outcome_from_tool_calls(proven).status == "completed"


def test_swarm_subtask_verified_needs_outcome_not_tool_success() -> None:
    from app.services.swarm_coordinator_service import _swarm_execution_verified

    read_only = [{"result": {"success": True, "action": "hubspot.contacts.search"}}]
    assert _swarm_execution_verified(["hubspot"], read_only) is True  # a read is its own proof
    unclassified = [{"result": {"success": True, "id": "1"}}]
    assert _swarm_execution_verified(["hubspot"], unclassified) is False
    unproven_write = [{"result": {"success": True, "action": "slack.post_message"}}]
    assert _swarm_execution_verified(["slack"], unproven_write) is False


def test_delegation_execution_verified_is_not_proof() -> None:
    from app.services.agent_delegation_strategy import delegation_observation
    from app.services.execution_plan_service import ExecutionPlan

    obs = delegation_observation(
        parent_plan_id="p",
        parent_step_id="s",
        child_plan=ExecutionPlan(plan_id="c", summary="child", source="test", steps=[]),
        result={
            "summary": "ok",
            "execution_verified": True,
            "tool_calls": [{"result": {"success": True, "action": "slack.post_message"}}],
        },
    )
    assert obs.structured["verified"] is False


# ---------------------------------------------------------------------------
# Finalizer scope + email truth
# ---------------------------------------------------------------------------


class _Table:
    def __init__(self, name: str) -> None:
        self.name = name
        self._payload: dict[str, Any] | None = None

    def insert(self, payload):
        self._payload = dict(payload)
        return self

    update = insert

    def select(self, *_a):
        return self

    def eq(self, *_a):
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        res = MagicMock()
        if self.name == "workflow_runs" and self._payload is None:
            res.data = [{"status": "running", "parameters": {}, "workflow_id": "wf-1"}]
        else:
            res.data = [dict(self._payload or {"workflow_id": "wf-1"})]
        return res


class _Client:
    def table(self, name: str) -> _Table:
        return _Table(name)


def _finalize(status: str, metadata: dict[str, Any], email_context: dict[str, Any] | None = None):
    from app.services.execution_outcome import finalize_execution_outcome

    with (
        patch("app.workflows.repository.update_run"),
        patch("app.workflows.repository.merge_run_parameters"),
        patch("app.workflows.repository.emit_execute_completed"),
        patch("app.services.notification_emitter.emit_notification") as emit,
    ):
        result = finalize_execution_outcome(
            _Client(),
            org_id="org-1",
            status=status,
            source="api",
            actor_id="11111111-1111-1111-1111-111111111111",
            run_id="22222222-2222-2222-2222-222222222222",
            channel_hints={"bell": True, "email": True},
            email_context=email_context,
            metadata=metadata,
        )
    return result, emit


def test_read_outcome_completes_without_write_evidence() -> None:
    result, _ = _finalize("completed", {"invoke_action": "hubspot.contacts.search"})
    assert result.status == "completed"


def test_unproven_write_cannot_complete() -> None:
    result, _ = _finalize("completed", {"invoke_action": "hubspot.contacts.update"})
    assert result.status == "verification_inconclusive"


def test_declared_consequential_outcome_needs_proof() -> None:
    result, _ = _finalize("completed", {"requires_outcome_verification": True})
    assert result.status == "verification_inconclusive"
    ok, _ = _finalize(
        "completed",
        {"requires_outcome_verification": True, "outcome_rollup": {"status": "completed", "unverified": 0}},
    )
    assert ok.status == "completed"


def test_completion_email_reports_coerced_status() -> None:
    _, emit = _finalize(
        "completed",
        {"invoke_action": "hubspot.contacts.update"},
        email_context={"kind": "workflow_completion", "run_id": "r", "final_status": "completed"},
    )
    sent_ctx = emit.call_args.kwargs.get("email_context") or {}
    assert sent_ctx.get("final_status") == "verification_inconclusive"


def test_partial_success_is_not_learned_as_success() -> None:
    from app.services.execution_outcome import _learning_event_for

    assert _learning_event_for("partial_success") != "workflow_executed"


@pytest.mark.parametrize(
    ("status", "needle"),
    [
        ("completed", "confirmed"),
        ("verification_inconclusive", "could not confirm"),
        ("partial_success", "some steps failing"),
        ("failed", "failed"),
    ],
)
def test_workflow_email_copy_matches_status(status: str, needle: str) -> None:
    from app.services import notification_email_service as svc

    captured: dict[str, Any] = {}

    def fake_simple(_brand, **kw):
        captured.update(kw)
        return "s", "<html/>"

    settings = MagicMock(notification_email_enabled=True)
    with (
        patch.object(svc, "email_notifications_enabled", return_value=True),
        patch.object(svc, "resolve_user_email", return_value="a@b.co"),
        patch.object(svc, "load_org_email_branding", return_value=MagicMock(app_base_url="https://x")),
        patch.object(svc, "_simple_completion_email", side_effect=fake_simple),
        patch.object(svc, "_send_email", return_value=True),
    ):
        svc.send_workflow_completion_email(
            MagicMock(), settings, org_id="o", user_id="u", run_id="r", workflow_name="W", final_status=status
        )
    assert needle in captured["summary"]
    if status != "completed":
        assert "successfully" not in captured["summary"]


def test_assignment_email_is_not_always_successful() -> None:
    from app.services import notification_email_service as svc

    captured: dict[str, Any] = {}
    settings = MagicMock(notification_email_enabled=True)
    with (
        patch.object(svc, "email_notifications_enabled", return_value=True),
        patch.object(svc, "resolve_user_email", return_value="a@b.co"),
        patch.object(svc, "load_org_email_branding", return_value=MagicMock(app_base_url="https://x")),
        patch.object(svc, "_simple_completion_email", side_effect=lambda _b, **kw: captured.update(kw) or ("s", "h")),
        patch.object(svc, "_send_email", return_value=True),
    ):
        svc.send_assignment_completion_email(
            MagicMock(),
            settings,
            org_id="o",
            user_id="u",
            job_id="j",
            task_title="T",
            requires_approval=False,
            final_status="verification_inconclusive",
        )
    assert "completed successfully" not in captured["summary"]
    assert "could not confirm" in captured["summary"]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _step(action: str, success: bool = True, verified: bool | None = None) -> dict[str, Any]:
    structured: dict[str, Any] = {}
    if verified is not None:
        structured["verification"] = {"verified": verified, "method": "entity_get"}
    return {"label": action, "invoke_action": action, "success": success, "structured": structured}


def test_orchestration_with_unproven_write_is_not_complete() -> None:
    from app.services.chat_orchestration_runs import orchestration_terminal_status

    steps = [_step("hubspot.contacts.search"), _step("hubspot.contacts.update")]
    assert orchestration_terminal_status(steps) == "verification_inconclusive"


def test_orchestration_four_of_five_is_partial_not_failed() -> None:
    from app.services.chat_orchestration_runs import orchestration_terminal_status

    steps = [_step("slack.post_message", verified=True) for _ in range(4)]
    steps.append(_step("hubspot.contacts.update", success=False))
    assert orchestration_terminal_status(steps) == "partial_success"


def test_orchestration_all_proven_completes() -> None:
    from app.services.chat_orchestration_runs import orchestration_terminal_status

    steps = [_step("hubspot.contacts.search"), _step("hubspot.contacts.update", verified=True)]
    assert orchestration_terminal_status(steps) == "completed"


# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------


def test_voice_never_says_done_without_proof() -> None:
    from app.services.pipecat_voice.voice_tool_narration import narrate_tool_completed

    said = narrate_tool_completed("update_contact", {"success": True})
    assert said is not None and "done" not in said.lower()
    proven = narrate_tool_completed(
        "update_contact",
        {"success": True, "verification": {"verified": True, "method": "entity_get"}},
    )
    assert proven is not None and "done" in proven.lower()


def test_voice_uncertain_write_is_not_called_a_failure_or_success() -> None:
    from app.services.pipecat_voice.voice_tool_narration import narrate_tool_completed

    said = narrate_tool_completed("update_contact", {"success": False, "error_code": "outcome_uncertain"})
    assert said is not None and "confirm" in said.lower()
