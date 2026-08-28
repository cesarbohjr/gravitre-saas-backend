"""Write-authority parity across every surface that can perform a connector write.

The parity proof previously covered chat direct-create only. These tests pin the
decision each surface actually makes, so a divergence becomes a failure rather
than an assumption.

Workflow steps are deliberately characterized, not asserted into parity — see
test_workflow_steps_do_not_consult_per_action_write_authority.
"""
from __future__ import annotations

import inspect

import pytest
from unittest.mock import MagicMock

from app.services.catalog_write_authority import (
    invoke_action_requires_write_approval,
    mcp_tool_requires_write_approval,
)
from app.services.react_write_gate import (
    PLATFORM_WRITE_TOOLS,
    tool_requires_user_write_approval,
)
from app.services.tool_registry import get_tool_registry

WRITE_SAMPLES = [
    ("hubspot_contacts_create", "hubspot.contacts.create"),
    ("slack_post_message", "slack.post_message"),
    ("notion_pages_create", "notion.pages.create"),
]
READ_TOOL, READ_ACTION = "hubspot_contacts_get", "hubspot.contacts.get"


@pytest.mark.parametrize(("tool_name", "invoke_action"), WRITE_SAMPLES)
def test_chat_react_gates_catalog_writes(tool_name, invoke_action):
    requires, resolved, _integration, _label = tool_requires_user_write_approval(
        tool_name, get_tool_registry()
    )
    assert requires is True
    assert resolved


def test_chat_react_does_not_gate_reads():
    requires, _action, _integration, _label = tool_requires_user_write_approval(
        READ_TOOL, get_tool_registry()
    )
    assert requires is False


def _mcp_registry(meta: dict) -> MagicMock:
    registry = MagicMock()
    registry.get_mcp_tool_meta.return_value = meta
    return registry


def test_mcp_write_routes_through_shared_authority():
    registry = _mcp_registry(
        {
            "capability_tier": "write",
            "requires_approval": True,
            "read_only_hint": False,
            "destructive_hint": False,
            "label": "Create record",
        }
    )
    requires, action, integration, _label = tool_requires_user_write_approval(
        "mcp_acme_create_record", registry
    )
    assert requires is True
    assert integration == "mcp"
    assert action == "mcp.mcp_acme_create_record"
    # Same verdict when the shared authority is consulted directly.
    assert (
        mcp_tool_requires_write_approval(
            capability_tier="write",
            requires_approval=True,
            read_only_hint=False,
            destructive_hint=False,
        )
        is True
    )


def test_mcp_read_is_not_gated():
    registry = _mcp_registry(
        {
            "capability_tier": "read",
            "requires_approval": False,
            "read_only_hint": True,
            "destructive_hint": False,
            "label": "List records",
        }
    )
    requires, _action, _integration, _label = tool_requires_user_write_approval(
        "mcp_acme_list_records", registry
    )
    assert requires is False


def test_extension_bridge_imports_shared_authority():
    import app.services.extension_bridge_service as ext

    assert "invoke_action_requires_write_approval" in inspect.getsource(ext)


@pytest.mark.parametrize(("tool_name", "invoke_action"), WRITE_SAMPLES)
def test_extension_bridge_agrees_with_chat(tool_name, invoke_action):
    """The bridge gates on invoke_action; chat gates on tool_name. Same verdict."""
    bridge = invoke_action_requires_write_approval(invoke_action)
    chat, _action, _integration, _label = tool_requires_user_write_approval(
        tool_name, get_tool_registry()
    )
    assert bridge is True
    assert bridge == chat


def test_extension_bridge_does_not_gate_reads():
    assert invoke_action_requires_write_approval(READ_ACTION) is False


def test_workflow_steps_do_not_consult_per_action_write_authority():
    """Characterizes a real gap: workflow steps have no per-action approval.

    Handlers call invoke_tool directly, and invoke_tool covers audit, rate
    limits, and agent permissions but not user write approval. Approval happens
    at the execution boundary instead, via assistant_execute_workflow.

    Scheduled dispatch does not cross that boundary, so a scheduled workflow
    performs connector writes with no run-time human approval. That is standing
    consent by authorship, not an approval gate. If per-step gating is ever
    added, this test should fail and be rewritten deliberately.
    """
    import app.workflows.handlers as handlers
    from app.services.tool_service import invoke_tool
    from app.services import workflow_schedule_service

    handlers_src = inspect.getsource(handlers)
    invoke_src = inspect.getsource(invoke_tool)
    schedule_src = inspect.getsource(workflow_schedule_service)

    for source in (handlers_src, invoke_src, schedule_src):
        assert "catalog_write_authority" not in source
        assert "requires_write_approval" not in source

    # The boundary gate is the only approval for workflow-driven writes.
    assert "assistant_execute_workflow" in PLATFORM_WRITE_TOOLS
