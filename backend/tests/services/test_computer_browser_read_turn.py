from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.computer_browser_read_turn import (
    match_computer_browser_followup,
    match_computer_browser_intent,
    try_computer_browser_read_turn,
)
from app.services.computer_execution import classify_execution_strategy, observation_from_browser_result
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep


def test_hubspot_write_stays_api_native() -> None:
    assert classify_execution_strategy(invoke_action="hubspot.contacts.create", has_action_spec=True) == "api_native"
    assert classify_execution_strategy(requires_graphical_ui=True, has_action_spec=False) == "browser_cdp"
    assert match_computer_browser_intent("How many HubSpot contacts are in this account?") is False
    assert match_computer_browser_intent("Create a HubSpot contact named Probe") is False
    assert (
        match_computer_browser_intent(
            "Open https://example.com in a browser. Do not use HubSpot."
        )
        is True
    )


def test_example_com_browser_intent() -> None:
    assert (
        match_computer_browser_intent(
            "Open https://example.com in a browser, tell me the title, then follow More information."
        )
        is True
    )


def test_followup_requires_computer_plan() -> None:
    state = {
        "execution_plan": {
            "plan_id": "p-browser",
            "source": "computer_execution",
            "terminal_status": "completed",
            "steps": [],
        },
        "work_artifacts": [{"artifact_id": "report:p-browser", "kind": "research_summary"}],
        "durable_deliverable": {"diagnosis": "Step 1"},
    }
    assert match_computer_browser_followup("What was the second page URL?", state) is True
    assert match_computer_browser_followup("What was the second page URL? Do not browse again.", state) is True
    assert match_computer_browser_followup("How many HubSpot contacts?", state) is False
    assert match_computer_browser_followup("What was the second page URL?", {}) is False


@pytest.mark.asyncio
async def test_computer_browser_binds_research_artifact_without_write() -> None:
    plan = ExecutionPlan(
        plan_id="plan-cu-1",
        summary="browse",
        source="computer_execution",
        steps=[ExecutionStep(step_id="computer_primary", title="read", kind="read")],
        execution_strategy="browser_cdp",
    )
    raw = {
        "success": True,
        "url": "https://www.iana.org/help/example-domains",
        "title": "Example Domains",
        "text": "This domain is for use in documentation examples.",
        "screenshot_digest": "deadbeef",
        "cdp_trace_id": "sess-1",
        "mode": "playwright_session_read",
        "strategy": "browser_cdp",
        "visits": [
            {
                "url": "https://example.com/",
                "title": "Example Domain",
                "action": "goto",
                "screenshot_digest": "aaa",
                "dom_excerpt": "Example Domain This domain is for use in illustrative examples",
            },
            {
                "url": "https://www.iana.org/help/example-domains",
                "title": "Example Domains",
                "action": "click_link",
                "screenshot_digest": "bbb",
                "dom_excerpt": "Example Domains",
                "link_text": "More information",
            },
        ],
    }
    obs = observation_from_browser_result(plan=plan, result=raw)
    with patch(
        "app.services.computer_browser_read_turn.execute_playwright_browser_read",
        new=AsyncMock(return_value=(raw, obs)),
    ):
        turn = await try_computer_browser_read_turn(
            message="Open example.com in a browser and follow the More information link.",
            task_state={},
        )
    assert turn is not None
    assert turn["writes_started"] is False
    assert turn["execution_path"] == "computer_browser_read"
    assert turn["execution_strategy"] == "browser_cdp"
    assert "httpx" not in turn["message"].lower()
    arts = turn["task_state"]["work_artifacts"]
    assert arts[-1]["kind"] == "research_summary"
    assert arts[-1]["metadata"]["exportable"] is True
    assert "example.com" in str(arts[-1]["metadata"]["code"]).lower()
    assert turn["task_state"]["execution_plan"]["source"] == "computer_execution"


@pytest.mark.asyncio
async def test_computer_browser_resume_does_not_reopen_browser() -> None:
    state = {
        "execution_plan": {
            "plan_id": "plan-cu-resume",
            "source": "computer_execution",
            "terminal_status": "completed",
            "steps": [],
        },
        "durable_deliverable": {
            "diagnosis": "Step 2 (click_link): Example Domains — https://www.iana.org/help/example-domains"
        },
        "work_artifacts": [
            {
                "artifact_id": "report:plan-cu-resume",
                "kind": "research_summary",
                "title": "Public web research summary",
                "preview": "Step 2",
                "metadata": {
                    "plan_id": "plan-cu-resume",
                    "outcome": "completed",
                    "code": "Step 2 (click_link): Example Domains — https://www.iana.org/help/example-domains",
                    "exportable": True,
                },
            }
        ],
    }
    with patch("app.services.computer_browser_read_turn.execute_playwright_browser_read") as mock_exec:
        turn = await try_computer_browser_read_turn(
            message="What was the second page URL?",
            task_state=state,
        )
    mock_exec.assert_not_called()
    assert turn is not None
    assert turn["execution_path"] == "computer_browser_read_resume"
    assert turn["provider_reinvoked"] is False
    assert turn["writes_started"] is False
    assert "iana.org" in turn["message"]
