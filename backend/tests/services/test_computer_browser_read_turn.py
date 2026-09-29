from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.computer_browser_read_turn import (
    match_computer_browser_followup,
    match_computer_browser_intent,
    match_computer_browser_resume_phrase,
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
        "computer_browser_evidence": {
            "mode": "playwright_session_read",
            "visits": [{"title": "Example Domain", "url": "https://example.com/", "action": "goto"}],
        },
        "durable_deliverable": {"diagnosis": "Step 1"},
    }
    assert match_computer_browser_followup("What was the second page URL?", state) is True
    assert match_computer_browser_followup("What was the second page URL? Do not browse again.", state) is True
    assert match_computer_browser_resume_phrase("What was the second page URL? Do not browse again.") is True
    assert match_computer_browser_resume_phrase("What was the title of the page we ended up on?") is True
    assert match_computer_browser_followup("How many HubSpot contacts?", state) is False
    assert match_computer_browser_followup("What was the second page URL?", {}) is False
    awaiting = {
        "execution_plan": {
            "plan_id": "p-interact",
            "source": "computer_execution",
            "terminal_status": "awaiting_confirm",
            "steps": [],
        }
    }
    assert match_computer_browser_followup("What was the second page URL?", awaiting) is False


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
        "computer_browser_evidence": {
            "mode": "playwright_session_read",
            "visits": [
                {"title": "Example Domain", "url": "https://example.com/", "action": "goto"},
                {
                    "title": "Example Domains",
                    "url": "https://www.iana.org/help/example-domains",
                    "action": "click_link",
                },
            ],
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


@pytest.mark.asyncio
async def test_computer_browser_resume_reloads_persisted_state() -> None:
    stored = {
        "execution_plan": {
            "plan_id": "plan-cu-reload",
            "source": "computer_execution",
            "terminal_status": "completed",
            "steps": [],
        },
        "durable_deliverable": {
            "diagnosis": "Step 2 (click_link): Example Domains — https://www.iana.org/help/example-domains"
        },
        "computer_browser_evidence": {
            "mode": "playwright_session_read",
            "visits": [
                {"title": "Example Domain", "url": "https://example.com/", "action": "goto"},
                {
                    "title": "Example Domains",
                    "url": "https://www.iana.org/help/example-domains",
                    "action": "click_link",
                },
            ],
        },
        "work_artifacts": [{"artifact_id": "report:plan-cu-reload", "kind": "research_summary"}],
    }
    svc = type("S", (), {})()
    svc.get_task_state = AsyncMock(return_value=stored)
    with patch(
        "app.services.conversation_state_service.get_conversation_state_service",
        return_value=svc,
    ):
        turn = await try_computer_browser_read_turn(
            message="What was the second page URL?",
            task_state={},
            conversation_id="conv-1",
            org_id="org",
            client=object(),
        )
    assert turn is not None
    assert turn["execution_path"] == "computer_browser_read_resume"
    assert "iana.org" in turn["message"]
    assert turn["provider_reinvoked"] is False


@pytest.mark.asyncio
async def test_computer_browser_resume_answers_url_and_title_from_visits() -> None:
    from app.services.computer_browser_read_turn import answer_from_computer_visits

    visits = [
        {"url": "https://example.com/", "title": "Example Domain", "action": "goto"},
        {"url": "https://www.iana.org/help/example-domains", "title": "Example Domains", "action": "click_link"},
    ]
    assert (
        answer_from_computer_visits("What was the second page URL? Do not browse again.", visits)
        == "https://www.iana.org/help/example-domains"
    )
    assert (
        answer_from_computer_visits("What was the title of the page we ended up on?", visits)
        == "Example Domains"
    )
    state = {
        "execution_observations": [
            {"success": True, "structured": {"visits": visits}},
        ]
    }
    with patch("app.services.computer_browser_read_turn.execute_playwright_browser_read") as mock_exec:
        turn = await try_computer_browser_read_turn(
            message="What was the second page URL? Do not browse again.",
            task_state=state,
        )
    mock_exec.assert_not_called()
    assert turn["message"] == "https://www.iana.org/help/example-domains"
    assert turn["provider_reinvoked"] is False


def test_browser_progress_streams_before_playwright_await() -> None:
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2] / "app" / "operators" / "agent_intelligence.py"
    ).read_text(encoding="utf-8")
    start = text.find('_mark("browser_session_start")')
    await_read = text.find("_computer_turn = await try_computer_browser_read_turn(")
    assert start > 0
    assert await_read > start
    assert "I'm opening a real browser session now" in text
    assert "_public_read_chromium" in (
        Path(__file__).resolve().parents[2] / "app" / "services" / "browser_agent_service.py"
    ).read_text(encoding="utf-8")
    assert "new_context(accept_downloads=False)" in (
        Path(__file__).resolve().parents[2] / "app" / "services" / "browser_agent_service.py"
    ).read_text(encoding="utf-8")
    session = (
        Path(__file__).resolve().parents[2] / "app" / "services" / "browser_agent_service.py"
    ).read_text(encoding="utf-8")
    helper_at = session.find("async def _click_public_follow_link")
    helper = session[helper_at : helper_at + 1600]
    assert helper_at > 0
    assert "if await link.count() == 0" in helper
    assert 'a[href*="iana.org"]' in helper
    assert helper.find("iana.org") < helper.find("get_by_role")


@pytest.mark.asyncio
async def test_click_prefers_iana_href_over_stale_visible_label() -> None:
    from app.services.browser_agent_service import _click_public_follow_link

    class _Loc:
        def __init__(self, n: int) -> None:
            self._n = n
            self.clicks = 0
            self.first = self

        async def count(self) -> int:
            return self._n

        async def click(self, timeout: int = 0) -> None:
            self.clicks += 1

    href = _Loc(1)
    more = _Loc(1)

    class _Page:
        def locator(self, _sel: str) -> _Loc:
            return href

        def get_by_role(self, _role: str, name: str | None = None) -> _Loc:
            return more

    ok, used, _err = await _click_public_follow_link(_Page(), follow_link_text="More information")
    assert ok is True
    assert used == "a[href*=iana.org]"
    assert href.clicks == 1
    assert more.clicks == 0


@pytest.mark.asyncio
async def test_click_learn_more_when_href_absent() -> None:
    from app.services.browser_agent_service import _click_public_follow_link

    class _Loc:
        def __init__(self, n: int) -> None:
            self._n = n
            self.clicks = 0
            self.first = self

        async def count(self) -> int:
            return self._n

        async def click(self, timeout: int = 0) -> None:
            self.clicks += 1

    href = _Loc(0)
    roles = {"Learn more": _Loc(1), "More information": _Loc(0)}

    class _Page:
        def locator(self, _sel: str) -> _Loc:
            return href

        def get_by_role(self, _role: str, name: str | None = None) -> _Loc:
            return roles.get(str(name or ""), _Loc(0))

    ok, used, _err = await _click_public_follow_link(_Page(), follow_link_text="More information")
    assert ok is True
    assert used == "Learn more"
    assert href.clicks == 0
    assert roles["Learn more"].clicks == 1
    assert roles["More information"].clicks == 0

