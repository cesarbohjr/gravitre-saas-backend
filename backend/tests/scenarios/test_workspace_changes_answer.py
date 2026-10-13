""""What changed in my workspace since yesterday?" gets the changes, not an offer.

Replays the 2026-10-12 incident end to end on both surfaces. The fake model
answers only from what the prompt gives it: with the workspace changes in its
context it summarises them; without them it does what production did, says it
lacks evidence and offers to check. So these tests fail on a polite non-answer,
not on wording.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest

from tests.scenarios.conversation_harness import ORG, USER, BrainCall, Reply, ScenarioHarness

NON_ANSWER = "I don't have evidence of workspace changes in this turn. I can check your activity if you want."
_OFFER = re.compile(r"(?i)\b(i can check|want me to|would you like me to|shall i|in this turn|say yes)\b")


def _answer_from_context(call: BrainCall) -> Reply:
    prompt = call.transcript()
    if "WORKSPACE CHANGES" not in prompt:
        return Reply(text=NON_ANSWER)
    runs = re.search(r"Weekly newsletter: failed — ([^\n]+)", prompt)
    if not runs:
        return Reply(text=NON_ANSWER)
    return Reply(text=f"Since yesterday, the Weekly newsletter run failed ({runs.group(1)}) and one run completed.")


def _seed(h: ScenarioHarness) -> None:
    # Inside "today" whatever the hour: two hours back crosses midnight
    # when the suite runs just after 00:00 UTC.
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    recent = max(now - timedelta(hours=2), midnight).isoformat()
    h.db.tables["workflow_defs"] = [{"id": "wf1", "org_id": ORG, "name": "Weekly newsletter"}]
    h.db.tables["workflow_runs"] = [
        {"org_id": ORG, "workflow_id": "wf1", "status": "completed", "run_type": "live", "created_at": recent},
        {"org_id": ORG, "workflow_id": "wf1", "status": "failed", "run_type": "live", "created_at": recent, "error_message": "HubSpot token expired"},
    ]
    h.db.tables["activity_events"] = []


@pytest.fixture
def stateful(monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.scenarios.conversation_harness as harness

    monkeypatch.setattr(
        harness,
        "STATEFUL_TABLES",
        harness.STATEFUL_TABLES | {"workflow_runs", "workflow_defs", "activity_events"},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["text", "voice"])
@pytest.mark.parametrize(
    "message",
    ["What changed in my workspace since yesterday?", "Catch me up on what happened today"],
)
async def test_workspace_changes_are_answered_not_offered(stateful: None, surface: str, message: str) -> None:
    searches: list[Any] = []

    async def _fake_search(*args: Any, **kwargs: Any) -> dict[str, Any]:
        searches.append((args, kwargs))
        return {"results": []}

    with ScenarioHarness() as h, patch("app.services.web_research.search_web", _fake_search):
        _seed(h)
        conv = h.conversation(surface)
        turn = await conv.say(message, _answer_from_context)

    assert "Weekly newsletter run failed (HubSpot token expired)" in turn.text, turn.text
    assert not _OFFER.search(turn.text), turn.text
    assert searches == []
    # The model saw the period it was answering for.
    assert any("Period:" in c.transcript() for c in turn.brain_calls)
