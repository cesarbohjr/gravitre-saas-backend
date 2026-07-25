"""Agent-on-canvas writes honor run-level catalog write authority."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings
from app.operators.react_engine import ReActEngine
from app.services.tool_types import ToolContext


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
    monkeypatch.setattr(
        "app.services.canvas_write_gate.load_run_for_write_gate",
        lambda *_a, **_k: {"id": "run1", "required_approvals": 1, "approval_status": "approved"},
    )

    ctx = ToolContext(
        settings=Settings(),
        client=MagicMock(),
        org_id="org",
        actor_id="user",
        run_id="run1",
    )
    result = await engine._execute_tool_call(ctx, "apollo_lists_create", {})
    assert result.get("success") is True
    engine.registry.execute_tool.assert_awaited_once()
