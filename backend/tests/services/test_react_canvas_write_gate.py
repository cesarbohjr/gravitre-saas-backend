"""Agent-on-canvas writes honor run-level catalog write authority."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings
from app.operators.react_engine import ReActEngine
from app.services.tool_types import ToolContext
from app.services.workflow_approval_scope import seal_approval_scope


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
async def test_canvas_run_approved_allows_write(monkeypatch):
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
    monkeypatch.setattr(
        "app.services.canvas_write_gate.load_run_for_write_gate",
        lambda *_a, **_k: {
            "id": "run1",
            "required_approvals": 1,
            "approval_status": "approved",
            "parameters": {"approval_scope": scope},
            "definition_snapshot": definition,
        },
    )

    ctx = ToolContext(
        settings=Settings(),
        client=MagicMock(),
        org_id="org",
        actor_id="user",
        run_id="run1",
    )
    result = await engine._execute_tool_call(
        ctx,
        "apollo_lists_create",
        {"name": "Outreach", "id": "list-1"},
    )
    assert result.get("success") is True
    engine.registry.execute_tool.assert_awaited_once()


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
