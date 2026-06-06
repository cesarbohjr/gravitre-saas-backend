from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.segment_tools import TOOL_EXECUTORS
from app.services.tool_types import ToolContext


def test_segment_tool_executors_registered():
    assert "segment.identify" in TOOL_EXECUTORS
    assert "segment.track" in TOOL_EXECUTORS
    assert "segment.group" in TOOL_EXECUTORS


def test_segment_track_success():
    settings = SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32, encryption_key="")
    ctx = ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-mkt",
        environment_name="production",
    )
    conn = {"id": "seg-conn", "type": "segment", "status": "active", "environment": "production"}
    with patch("app.services.segment_tools.get_connector_by_type", return_value=conn):
        with patch("app.services.segment_tools.enforce_rate_limit"):
            with patch(
                "app.services.segment_tools.resolve_segment_write_key",
                return_value="wk_test",
            ):
                with patch("app.services.segment_tools.track", return_value={"success": True}):
                    result = TOOL_EXECUTORS["segment.track"](
                        ctx,
                        {"user_id": "u1", "event": "Signed Up"},
                    )
    assert result.success is True
