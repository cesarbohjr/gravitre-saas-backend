"""Unified write authority for native catalog and MCP tools."""
from __future__ import annotations

from app.services.catalog_write_authority import (
    mcp_hints_from_schema,
    mcp_tool_requires_write_approval,
)
from app.services.react_write_gate import tool_requires_user_write_approval
from app.services.tool_registry import ToolRegistry


def test_mcp_hints_from_schema_annotations():
    schema = {
        "type": "object",
        "annotations": {"readOnlyHint": False, "destructiveHint": True},
        "properties": {},
    }
    ro, de = mcp_hints_from_schema(schema)
    assert ro is False
    assert de is True
    assert mcp_tool_requires_write_approval(destructive_hint=de) is True


def test_mcp_read_only_hint_skips_write_gate():
    assert (
        mcp_tool_requires_write_approval(
            capability_tier="write",
            read_only_hint=True,
        )
        is False
    )


def test_react_write_gate_mcp_destructive_requires_approval():
    registry = ToolRegistry()
    registry._mcp_meta["mcp_acme_delete_item"] = {
        "capability_tier": "write",
        "requires_approval": True,
        "read_only_hint": False,
        "destructive_hint": True,
        "label": "Delete item",
    }
    requires, action, integration, label = tool_requires_user_write_approval(
        "mcp_acme_delete_item", registry
    )
    assert requires is True
    assert action == "mcp.mcp_acme_delete_item"
    assert integration == "mcp"
    assert "Delete" in label
