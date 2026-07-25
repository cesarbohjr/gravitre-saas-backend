"""Meson conversational edit — heuristic path + diff proposal."""
from __future__ import annotations

import pytest

from app.services.meson_canvas_edit import _heuristic_edit, _builder_snapshot


def test_heuristic_removes_slack_step():
    graph = {
        "nodes": [
            {"id": "1", "name": "Ingest", "type": "source"},
            {"id": "2", "name": "Slack Notification", "type": "connector", "vendor": "slack"},
        ],
        "edges": [{"id": "e1", "from_node_id": "1", "to_node_id": "2"}],
    }
    after, conf = _heuristic_edit("remove the Slack notification step", graph)
    assert conf >= 0.5
    names = [n["name"] for n in after["nodes"]]
    assert "Slack Notification" not in names
    assert "Ingest" in names


def test_heuristic_adds_hubspot_check():
    graph = _builder_snapshot(
        [{"id": "1", "name": "Send email", "type": "connector", "config": {}}],
        [],
    )
    after, conf = _heuristic_edit("add a step that checks HubSpot before sending", graph)
    assert conf >= 0.5
    assert any("HubSpot" in str(n.get("name")) for n in after["nodes"])


def test_heuristic_schedule_morning():
    graph = {"nodes": [{"id": "1", "name": "Job", "type": "task"}], "edges": []}
    after, _conf = _heuristic_edit("change this to run every morning instead of every hour", graph)
    assert after.get("schedule", {}).get("cron") == "0 9 * * *"


@pytest.mark.asyncio
async def test_propose_edit_requires_workflow(monkeypatch):
    from unittest.mock import MagicMock

    from app.services import meson_canvas_edit as mod

    monkeypatch.setattr(mod, "get_workflow_def", lambda *_a, **_k: None)
    with pytest.raises(ValueError, match="not found"):
        await mod.propose_workflow_edit(
            client=MagicMock(),
            settings=MagicMock(),
            org_id="org",
            workflow_id="wf",
            environment_name="default",
            instruction="add approval",
        )
