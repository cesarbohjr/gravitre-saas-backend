"""Offered READ continuation: yes must execute, not acknowledge."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.services.offered_action_continuation import (
    claims_future_action,
    extract_offered_action,
    is_confirm_utterance,
    offered_from_state,
    resolve_offered_action_turn,
    synthesize_health_findings,
)


OFFER = (
    "I don’t have enough information yet to say what needs attention. "
    "If you want, I can check connector health, recent workflow runs, or org analytics."
)


def test_extract_offer_from_screenshot_copy() -> None:
    offered = extract_offered_action(OFFER)
    assert offered is not None
    assert offered.status == "awaiting_user_confirmation"
    assert "connectors" in offered.scope
    assert "workflows" in offered.scope
    assert "analytics" in offered.scope
    assert "connector_status" in offered.tools
    assert "workflow_runs" in offered.tools
    assert "analytics" in offered.tools


def test_yes_resolves_to_execute_against_stored_offer() -> None:
    offered = extract_offered_action(OFFER)
    assert offered is not None
    decision = resolve_offered_action_turn(
        "yes",
        task_state={"offered_action": offered.as_dict(), "pending_task": None},
    )
    assert decision.kind == "execute_read"
    assert decision.offered is not None
    assert decision.offered.tools == offered.tools


@pytest.mark.parametrize("utterance", ["yes", "yep", "sure", "go ahead", "please do", "okay", "ok"])
def test_confirm_tokens(utterance: str) -> None:
    assert is_confirm_utterance(utterance) is True


def test_no_does_not_execute() -> None:
    offered = extract_offered_action(OFFER)
    assert offered is not None
    decision = resolve_offered_action_turn(
        "no",
        task_state={"offered_action": offered.as_dict()},
    )
    assert decision.kind == "decline"


def test_topic_change_does_not_execute() -> None:
    offered = extract_offered_action(OFFER)
    assert offered is not None
    decision = resolve_offered_action_turn(
        "Draft a follow-up email to Stephanie",
        task_state={"offered_action": offered.as_dict()},
    )
    assert decision.kind == "topic_change"


def test_write_pending_owns_yes() -> None:
    offered = extract_offered_action(OFFER)
    assert offered is not None
    decision = resolve_offered_action_turn(
        "yes",
        task_state={
            "offered_action": offered.as_dict(),
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_confirm",
                "params": {"invoke_action": "gmail.send"},
            },
        },
    )
    assert decision.kind == "none"
    assert decision.reason == "pending_write_owns_confirm"


def test_history_fallback_when_offer_was_not_persisted() -> None:
    decision = resolve_offered_action_turn(
        "yes",
        task_state={"pending_task": None},
        conversation_history=[
            {"role": "user", "content": "What needs attention?"},
            {"role": "assistant", "content": OFFER},
        ],
    )
    assert decision.kind == "execute_read"
    assert decision.offered is not None
    assert "connector_status" in decision.offered.tools


def test_claims_future_action_on_ack() -> None:
    assert claims_future_action("Got it — I’ll check what needs attention.") is True
    assert claims_future_action(OFFER) is False


def test_zero_findings_is_clean() -> None:
    text = synthesize_health_findings(
        [
            {"name": "connector_status", "output": {"connectors": []}},
            {"name": "workflow_runs", "output": {"runs": [], "total": 0}},
            {"name": "agent_status", "output": {"agents": []}},
            {"name": "analytics", "output": {"openAlerts": 0, "last7Days": {"statusBreakdown": {}}}},
        ]
    )
    assert "didn't find anything urgent" in text.lower()
    assert "json" not in text.lower()
    assert "{" not in text


def test_timeout_is_explicit_failure() -> None:
    text = synthesize_health_findings(
        [{"name": "connector_status", "output": {"error": "timeout"}}],
        timed_out=["connector health"],
    )
    assert "couldn't complete" in text.lower() or "timed out" in text.lower()
    assert "I'll check" not in text


def test_write_offer_is_not_read_continuation() -> None:
    assert (
        extract_offered_action("If you want, I can send Stephanie the email now.")
        is None
    )


@pytest.mark.asyncio
async def test_execute_calls_all_read_tools() -> None:
    from app.services.offered_action_continuation import execute_offered_read

    offered = extract_offered_action(OFFER)
    assert offered is not None

    async def _fake_tools(requested: list[str], *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        name = requested[0]
        outputs = {
            "connector_status": {"connectors": []},
            "workflow_runs": {"runs": [{"workflowName": "Lead routing", "status": "failed"}]},
            "agent_status": {"agents": []},
            "analytics": {"openAlerts": 0, "last7Days": {"statusBreakdown": {}}},
        }
        return [{"name": name, "output": outputs[name]}]

    with patch(
        "app.services.assistant_tools.run_assistant_tools",
        new=AsyncMock(side_effect=_fake_tools),
    ):
        executed = await execute_offered_read(
            offered,
            org_id="org",
            settings=object(),
        )
    names = [row["name"] for row in executed["tool_results"]]
    assert "connector_status" in names
    assert "workflow_runs" in names
    assert executed["terminal_state"] == "COMPLETED"
    assert "Lead routing" in executed["message"]
    assert "I'll check" not in executed["message"]


def test_offered_from_state_ignores_completed() -> None:
    assert offered_from_state({"offered_action": {"status": "completed", "tools": ["connector_status"]}}) is None
