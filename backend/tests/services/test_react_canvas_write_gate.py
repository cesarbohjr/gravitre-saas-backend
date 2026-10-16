"""Agent-on-canvas writes honor run-level catalog write authority."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings
from app.operators.react_engine import ReActEngine
from app.services.tool_types import ToolContext
from app.services.workflow_approval_scope import seal_approval_scope


class ProjectedRunClient:
    """Model PostgREST projection instead of returning unselected columns."""

    def __init__(self, row):
        self.row = row
        self.columns = []
        self.filters = {}

    def table(self, name):
        assert name == "workflow_runs"
        return self

    def select(self, columns):
        self.columns = [column.strip() for column in columns.split(",")]
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def limit(self, value):
        assert value == 1
        return self

    def execute(self):
        matches = all(self.row.get(key) == value for key, value in self.filters.items())
        return SimpleNamespace(data=[{key: self.row.get(key) for key in self.columns}] if matches else [])


@pytest.mark.asyncio
async def test_canvas_run_unapproved_blocks_write(monkeypatch):
    engine = ReActEngine.__new__(ReActEngine)
    engine.registry = MagicMock()
    engine.registry.execute_tool = AsyncMock(return_value={"success": True})

    monkeypatch.setattr(
        "app.services.react_write_gate.tool_requires_user_write_approval",
        lambda *_a, **_k: (True, "apollo.lists.create", "apollo", "Create list"),
    )
    monkeypatch.setattr(
        "app.services.canvas_write_gate.load_run_for_write_gate",
        lambda *_a, **_k: {"id": "run1", "required_approvals": 1, "approval_status": "pending_approval"},
    )

    ctx = ToolContext(
        settings=Settings(),
        client=MagicMock(),
        org_id="org",
        actor_id="user",
        run_id="run1",
    )
    result = await engine._execute_tool_call(ctx, "apollo_lists_create", {})
    assert result["success"] is False
    assert result["error_code"] == "canvas_write_authority_blocked"
    engine.registry.execute_tool.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [None, "arguments", "definition"])
async def test_canvas_run_approved_uses_projected_reviewed_definition(monkeypatch, change):
    engine = ReActEngine.__new__(ReActEngine)
    engine.registry = MagicMock()
    engine.registry.execute_tool = AsyncMock(return_value={"success": True, "ok": True})

    monkeypatch.setattr(
        "app.services.react_write_gate.tool_requires_user_write_approval",
        lambda *_a, **_k: (True, "apollo.lists.create", "apollo", "Create list"),
    )
    definition = {
        "steps": [
            {
                "id": "s1",
                "type": "invoke_tool",
                "config": {"action": "apollo.lists.create", "name": "Outreach", "id": "list-1"},
            }
        ]
    }
    scope = seal_approval_scope(definition)
    row = {
        "id": "run1", "org_id": "org",
        "required_approvals": 1, "approval_status": "approved",
        "parameters": {"approval_scope": scope},
        "definition_snapshot": deepcopy(definition),
    }
    args = {"name": "Outreach", "id": "list-1"}
    if change == "arguments":
        args["name"] = "Unreviewed list"
    if change == "definition":
        row["definition_snapshot"]["steps"][0]["config"]["name"] = "Unreviewed list"
    client = ProjectedRunClient(row)
    ctx = ToolContext(
        settings=Settings(), client=client, org_id="org", actor_id="user", run_id="run1",
    )
    result = await engine._execute_tool_call(
        ctx,
        "apollo_lists_create",
        args,
    )
    assert client.filters == {"id": "run1", "org_id": "org"}
    assert "definition_snapshot" in client.columns
    if change is None:
        assert result.get("success") is True
        engine.registry.execute_tool.assert_awaited_once()
    else:
        assert result["success"] is False
        engine.registry.execute_tool.assert_not_awaited()
        assert result["reason"] == (
            "approval_scope_args_mismatch" if change == "arguments" else "approval_scope_digest_mismatch"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [
    {"connector_id": "other"}, {"path": "/execute"}, {"headers": {"X-Action": "execute"}},
])
async def test_changed_webhook_effect_never_reaches_provider(monkeypatch, change):
    engine = ReActEngine.__new__(ReActEngine)
    engine.registry = MagicMock()
    engine.registry.execute_tool = AsyncMock(return_value={"success": True})
    approved = {"connector_id": "reviewed", "path": "/preview", "headers": {"X-Action": "preview"}, "payload": {"amount": 10}}
    definition = {"steps": [{"type": "invoke_tool", "config": {"action": "webhook.post", "params": approved}}]}
    monkeypatch.setattr("app.services.react_write_gate.tool_requires_user_write_approval", lambda *_a, **_k: (True, "webhook.post", "webhook", "Send webhook"))
    monkeypatch.setattr("app.services.canvas_write_gate.load_run_for_write_gate", lambda *_a, **_k: {
        "required_approvals": 1, "approval_status": "approved", "definition_snapshot": definition,
        "parameters": {"approval_scope": seal_approval_scope(definition)},
    })
    ctx = ToolContext(settings=Settings(), client=MagicMock(), org_id="org", actor_id="user", run_id="run")
    result = await engine._execute_tool_call(ctx, "webhook_post", {**approved, **change})
    assert result["success"] is False
    assert result["reason"] == "approval_scope_args_mismatch"
    engine.registry.execute_tool.assert_not_awaited()


def test_write_gate_loader_does_not_return_another_org_run():
    from app.services.canvas_write_gate import load_run_for_write_gate

    client = ProjectedRunClient({"id": "run1", "org_id": "another-org"})
    assert load_run_for_write_gate(client, "org", "run1") is None
    assert client.filters == {"id": "run1", "org_id": "org"}
