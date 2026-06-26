"""ReActEngine streaming wrapper parity tests."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.operators.react_engine import ReActEngine, ReActStatus
from app.services.tool_types import ToolContext


def _settings() -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
    )


def _tool_call(name: str, arguments: str, call_id: str = "tc1"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _model_response(*, content: str = "", tool_calls: list | None = None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


@pytest.mark.asyncio
async def test_execute_streaming_yields_same_tool_calls_as_execute():
    engine = ReActEngine(settings=_settings(), registry=MagicMock())
    engine.registry.get_tools_for_agent = MagicMock(
        return_value=[{"type": "function", "function": {"name": "web_search", "parameters": {}}}]
    )
    engine.registry.list_connected_integrations = MagicMock(return_value=["platform"])
    engine.registry.execute_tool = AsyncMock(
        return_value={"success": True, "tool": "web_search", "results": [], "totalResults": 0, "query": "news"}
    )

    ctx = ToolContext(
        settings=_settings(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
    )

    model_sequence = [
        _model_response(tool_calls=[_tool_call("web_search", '{"query":"news"}')]),
        _model_response(content="Final answer"),
    ]

    with patch.object(engine, "_chat_with_tools", AsyncMock(side_effect=model_sequence)):
        with patch("app.operators.react_engine.moderate_input", AsyncMock()):
            sync_result = await engine.run(
                ctx=ctx,
                task="Find news",
                system_prompt="sys",
                permitted_tools=["web_search"],
                connected_integrations=["platform"],
                max_iterations=3,
            )

    stream_sequence = [
        _model_response(tool_calls=[_tool_call("web_search", '{"query":"news"}')]),
        _model_response(content="Final answer"),
    ]
    tool_events: list[str] = []
    with patch.object(engine, "_chat_with_tools", AsyncMock(side_effect=stream_sequence)):
        with patch("app.operators.react_engine.moderate_input", AsyncMock()):
            async for event in engine.run_streaming(
                ctx=ctx,
                task="Find news",
                system_prompt="sys",
                permitted_tools=["web_search"],
                connected_integrations=["platform"],
                max_iterations=3,
            ):
                if event.kind == "tool_start":
                    tool_events.append(event.tool_name or "")
                if event.kind == "done":
                    stream_result = event.react_result

    sync_tools = [call.get("tool") for call in sync_result.tool_calls]
    stream_tools = [call.get("tool") for call in (stream_result.tool_calls or [])]
    assert sync_tools == stream_tools == ["web_search"]
    assert sync_result.status == stream_result.status == ReActStatus.COMPLETED
    assert tool_events == ["web_search"]
