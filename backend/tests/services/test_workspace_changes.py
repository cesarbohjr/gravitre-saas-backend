"""Workspace change questions read the workspace's own dated records.

2026-10-12 incident: "what changed in my workspace since yesterday?" reached
the model with no dated workspace evidence, ran two public web searches, and
came back offering to check. These tests pin the period, the per-source
outcome (found / nothing / could not be read) and the prompt block the model
answers from.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from app.services import workspace_changes as wc
from app.services.workspace_changes import (
    is_workspace_change_question,
    read_workspace_changes,
    resolve_change_window,
)
from tests.scenarios.conversation_harness import ORG, USER, ScenarioDB

# Monday 2026-10-12 21:00 UTC = 14:00 in Los Angeles.
NOW = datetime(2026, 10, 12, 21, 0, tzinfo=timezone.utc)
LA = "America/Los_Angeles"


@pytest.mark.parametrize(
    "message",
    [
        "What changed in my workspace since yesterday?",
        "what happened in our workspace today",
        "Any changes to my workflows this week?",
        "Catch me up",
        "What did I miss?",
        "what's new with my approvals",
    ],
)
def test_change_questions_are_recognised(message: str) -> None:
    assert is_workspace_change_question(message)


@pytest.mark.parametrize(
    "message",
    [
        "What changed in the news about OpenAI yesterday?",
        "What happened with Ukraine this week?",
        "Write me an email to Dana",
        "What's 2 plus 2?",
        "What changed in the industry average for open rates?",
    ],
)
def test_other_questions_are_not(message: str) -> None:
    assert not is_workspace_change_question(message)


@pytest.mark.parametrize(
    ("message", "start_local", "label"),
    [
        ("what changed since yesterday", "2026-10-11T00:00", "since the start of yesterday"),
        ("anything new today", "2026-10-12T00:00", "since midnight today"),
        ("what happened last night", "2026-10-11T18:00", "since 6 PM yesterday"),
        ("any changes this week", "2026-10-12T00:00", "since Monday"),
        ("what changed in the last 3 hours", "2026-10-12T11:00", "the last 3 hours"),
        ("what changed in my workspace", "2026-10-11T14:00", "the last 24 hours"),
    ],
)
def test_window_is_resolved_in_the_org_time_zone(message: str, start_local: str, label: str) -> None:
    w = resolve_change_window(message, tz_name=LA, now=NOW)
    assert w.start.strftime("%Y-%m-%dT%H:%M") == start_local
    assert w.label == label
    assert w.tz_name == LA


def test_bad_time_zone_falls_back_to_utc() -> None:
    w = resolve_change_window("what changed today", tz_name="Not/AZone", now=NOW)
    assert w.tz_name == "UTC"
    assert w.start == datetime(2026, 10, 12, tzinfo=timezone.utc)


def _seeded_db() -> ScenarioDB:
    db = ScenarioDB()
    db.tables["workflow_defs"] = [{"id": "wf1", "org_id": ORG, "name": "Weekly newsletter"}]
    db.tables["workflow_runs"] = [
        {"org_id": ORG, "workflow_id": "wf1", "status": "completed", "run_type": "live", "created_at": "2026-10-12T16:05:00+00:00"},
        {"org_id": ORG, "workflow_id": "wf1", "status": "failed", "run_type": "live", "created_at": "2026-10-12T17:30:00+00:00", "error_message": "HubSpot token expired"},
        # Before the window: not a change since yesterday.
        {"org_id": ORG, "workflow_id": "wf1", "status": "completed", "run_type": "live", "created_at": "2026-10-09T10:00:00+00:00"},
        # Another org's run never leaks in.
        {"org_id": "other-org", "workflow_id": "wf1", "status": "failed", "run_type": "live", "created_at": "2026-10-12T17:00:00+00:00"},
    ]
    db.tables["activity_events"] = [
        {"org_id": ORG, "user_id": USER, "title": "Sent email to Dana", "status": "completed", "integration": "gmail", "created_at": "2026-10-12T15:00:00+00:00"},
        {"org_id": ORG, "user_id": "someone-else", "title": "Private action", "status": "completed", "created_at": "2026-10-12T15:00:00+00:00"},
    ]
    return db


@pytest.fixture
def stateful(monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.scenarios.conversation_harness as harness

    monkeypatch.setattr(
        harness,
        "STATEFUL_TABLES",
        harness.STATEFUL_TABLES | {"workflow_runs", "workflow_defs", "activity_events", "goals", "audit_events"},
    )


@pytest.mark.asyncio
async def test_reads_each_source_for_the_period(stateful: None) -> None:
    changes = await read_workspace_changes(
        _seeded_db(), ORG, "what changed since yesterday?", user_id=USER, tz_name=LA, now=NOW
    )
    by_name = {s.name: s for s in changes.sources}
    runs = by_name["Workflow runs"]
    assert runs.status == "read" and runs.total == 2
    # The failure leads, with its reason and local time.
    assert runs.items[0] == "By status: 1 completed, 1 failed"
    assert "Weekly newsletter: failed — HubSpot token expired" in runs.items[1]
    assert runs.items[1].startswith("Mon 10:30 AM")
    activity = by_name["Your connected-app actions"]
    assert activity.total == 1 and "Sent email to Dana in gmail" in activity.items[0]
    assert by_name["Goals"].status == "read" and by_name["Goals"].total == 0

    block = changes.to_prompt_block()
    assert block.startswith("WORKSPACE CHANGES")
    assert "Period: since the start of yesterday — Sun Oct 11, 12:00 AM to Mon Oct 12, 2:00 PM (America/Los_Angeles)." in block
    assert "- Goals: nothing recorded in this period." in block
    assert "Private action" not in block
    assert "do not offer to check them" in block
    assert "Could not be read" not in block


@pytest.mark.asyncio
async def test_a_failed_source_is_reported_not_hidden(stateful: None, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a: Any) -> Any:
        raise RuntimeError("relation does not exist")

    monkeypatch.setattr(wc, "_SOURCES", (("Workflow runs", wc._read_workflow_runs), ("Audit log", _boom)))
    changes = await read_workspace_changes(_seeded_db(), ORG, "what changed today", user_id=USER, tz_name=LA, now=NOW)
    assert [s.status for s in changes.sources] == ["read", "failed"]
    assert "Could not be read this time: Audit log." in changes.to_prompt_block()
    assert changes.to_meta()["sources"]["Audit log"] == {"status": "failed", "total": 0}


@pytest.mark.asyncio
async def test_a_slow_source_does_not_hold_the_answer(stateful: None, monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    def _slow(*_a: Any) -> Any:
        time.sleep(0.5)
        return 0, []

    monkeypatch.setattr(wc, "SOURCE_TIMEOUT_S", 0.05)
    monkeypatch.setattr(wc, "_SOURCES", (("Audit log", _slow),))
    changes = await asyncio.wait_for(
        read_workspace_changes(_seeded_db(), ORG, "what changed today", user_id=USER, tz_name=LA, now=NOW), 0.4
    )
    assert changes.sources[0].status == "failed"


@pytest.mark.asyncio
async def test_activity_without_a_user_is_not_read_as_empty(stateful: None) -> None:
    changes = await read_workspace_changes(_seeded_db(), ORG, "what changed today", user_id="", tz_name=LA, now=NOW)
    activity = next(s for s in changes.sources if s.name == "Your connected-app actions")
    assert activity.status == "failed"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("What changed in my workspace since yesterday?", True),
        ("Did any of my workflow runs fail today?", True),
        ("yes", False),
        ("Send the update to my team", False),
        ("What's the latest news about OpenAI?", False),
    ],
)
def test_a_read_the_user_asked_for_is_not_offered_back(message: str, expected: bool) -> None:
    from app.services.offered_action_continuation import user_requested_read

    assert user_requested_read(message) is expected


def test_a_workspace_question_does_not_accept_an_open_offer() -> None:
    from app.services.offered_action_continuation import resolve_offered_action_turn

    state = {"offered_action": {"id": "o1", "scope": ["workflows", "connectors"], "status": "awaiting_user_confirmation"}}
    asked = resolve_offered_action_turn("What changed in my workspace since yesterday?", task_state=state)
    assert asked.kind == "topic_change"
    # A real acceptance still runs the offered check.
    assert resolve_offered_action_turn("yes please", task_state=state).kind == "execute_read"
    assert resolve_offered_action_turn("sure, check it", task_state=state).kind == "execute_read"
