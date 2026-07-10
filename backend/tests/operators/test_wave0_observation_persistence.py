"""Wave 0 #2 — durable tool observation/args/error on audits + conversation tool_calls."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operators.agent_intelligence import _tool_results_from_connector_turn
from app.operators.assistant_sse import format_react_tool_output
from app.operators.react_engine import ReActEngine, ReActStatus
from app.services.tool_types import ToolContext


def test_tool_results_from_connector_execution_include_args_and_body():
    results = _tool_results_from_connector_turn(
        {
            "execution_result": {
                "success": True,
                "title": "Create Apollo contact list",
                "body": "Created list “MSP Prospects” (id list-123).",
                "result_url": None,
                "connector_management_url": "/connectors/conn-1",
                "integration": "apollo",
                "structured": {"label": {"id": "list-123", "name": "MSP Prospects"}},
                "task_label": "Create Apollo contact list",
            },
            "connector_tool": {
                "tool_name": "apollo_lists_create",
                "invoke_action": "apollo.lists.create",
                "label": "Create Apollo contact list",
                "args": {"name": "MSP Prospects", "modality": "contacts"},
            },
        }
    )
    assert len(results) == 1
    assert results[0]["name"] == "apollo_lists_create"
    assert results[0]["input"]["name"] == "MSP Prospects"
    assert results[0]["output"]["success"] is True
    assert "MSP Prospects" in results[0]["output"]["body"]
    assert results[0]["output"]["invokeAction"] == "apollo.lists.create"


def test_tool_results_from_approval_pending_include_error_code():
    results = _tool_results_from_connector_turn(
        {
            "pending_task": {
                "type": "connector_action",
                "params": {
                    "tool_name": "apollo_lists_create",
                    "invoke_action": "apollo.lists.create",
                    "label": "Create Apollo contact list",
                    "args": {"name": "MSP Prospects"},
                },
            },
            "task_state": {
                "pending_task": {
                    "type": "connector_action",
                    "status": "awaiting_confirm",
                    "params": {
                        "tool_name": "apollo_lists_create",
                        "invoke_action": "apollo.lists.create",
                        "label": "Create Apollo contact list",
                        "args": {"name": "MSP Prospects"},
                    },
                }
            },
        }
    )
    assert len(results) == 1
    assert results[0]["errorCode"] == "write_approval_required"
    assert results[0]["input"]["name"] == "MSP Prospects"


def test_format_react_tool_output_includes_error_code():
    shaped = format_react_tool_output(
        "apollo_lists_create",
        {"success": False, "error": "boom", "error_code": "permission_denied"},
    )
    assert shaped["error"] == "boom"
    assert shaped["errorCode"] == "permission_denied"
    assert shaped["success"] is False


@pytest.mark.asyncio
async def test_react_tool_audit_includes_args_observation_and_error():
    settings = SimpleNamespace(disable_ai=False, ai_pii_redaction_enabled=False)
    registry = MagicMock()
    registry.list_connected_integrations.return_value = ["hubspot"]
    registry.get_available_tools = AsyncMock(
        return_value=[{"type": "function", "function": {"name": "hubspot_search_contacts"}}]
    )
    registry.execute_tool = AsyncMock(
        return_value={"success": False, "error": "rate limited", "error_code": "rate_limited"}
    )
    engine = ReActEngine(settings=settings, registry=registry)
    engine.router = MagicMock()
    engine.router._openai = AsyncMock()

    def _choice(content: str = "", tool_calls: list | None = None):
        message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
        return SimpleNamespace(message=message, finish_reason="stop")

    def _tool_call(name: str, args: str, call_id: str = "call-1"):
        fn = SimpleNamespace(name=name, arguments=args)
        return SimpleNamespace(id=call_id, function=fn)

    engine.router._openai.chat.completions.create = AsyncMock(
        side_effect=[
            SimpleNamespace(
                choices=[
                    _choice(
                        "Searching.",
                        tool_calls=[_tool_call("hubspot_search_contacts", '{"query":"acme"}')],
                    )
                ]
            ),
            SimpleNamespace(choices=[_choice("Could not finish.")]),
        ]
    )
    ctx = ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-1",
        task_id="job-1",
    )
    with patch("app.operators.react_engine.moderate_input", new=AsyncMock()), patch(
        "app.operators.react_engine.write_audit_event"
    ) as audit_mock, patch(
        "app.services.react_write_gate.block_react_write_execution", return_value=None
    ):
        result = await engine.run(
            ctx=ctx,
            task="Find contact",
            permitted_tools=["hubspot"],
            connected_integrations=["hubspot"],
            max_iterations=5,
            audit_resource_id="job-1",
        )

    assert result.status == ReActStatus.COMPLETED
    tool_audits = [
        call.kwargs["metadata"]
        for call in audit_mock.call_args_list
        if call.kwargs.get("metadata", {}).get("status") == "tool_call"
    ]
    assert len(tool_audits) == 1
    meta = tool_audits[0]
    assert meta["toolArgs"] == {"query": "acme"}
    assert meta["error"] == "rate limited"
    assert meta["errorCode"] == "rate_limited"
    assert meta["toolSuccess"] is False
    assert "rate limited" in (meta["observation"] or "")
