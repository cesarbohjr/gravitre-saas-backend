from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.tool_registry import ToolRegistry, get_tool_registry
from app.services.tool_service import list_registered_actions
from app.services.tool_types import NormalizedResult, ToolContext


@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry()


@pytest.fixture
def tool_ctx() -> ToolContext:
    settings = SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32)
    return ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-1",
    )


def test_all_registry_actions_exist_in_tool_service(registry: ToolRegistry):
    registered = set(list_registered_actions())
    missing: list[str] = []
    for name in registry.list_tool_names():
        spec = registry.get_spec(name)
        assert spec is not None
        if spec.name.startswith("assistant_"):
            continue
        if spec.always_available:
            continue
        action = spec.invoke_action
        if spec.name == "salesforce_update_record":
            for sf_action in (
                "salesforce.leads.update",
                "salesforce.opportunities.update",
                "salesforce.accounts.update",
            ):
                assert sf_action in registered
            continue
        if action not in registered:
            missing.append(f"{name} -> {action}")
    assert not missing, f"Missing invoke_tool actions: {missing}"


def test_get_tools_for_agent_filters_by_connection(registry: ToolRegistry):
    tools = registry.get_tools_for_agent(
        permitted_tools=["hubspot", "slack"],
        connected_integrations=["hubspot"],
    )
    names = {t["function"]["name"] for t in tools}
    assert "hubspot_search_contacts" in names
    assert "slack_send_message" not in names
    assert "web_search" in names


def test_get_tools_for_agent_respects_permitted_prefix(registry: ToolRegistry):
    tools = registry.get_tools_for_agent(
        permitted_tools=["slack"],
        connected_integrations=["slack"],
    )
    names = {t["function"]["name"] for t in tools}
    assert names == {"slack_send_message", "web_search"}


def test_get_tools_for_agent_all_wildcard(registry: ToolRegistry):
    tools = registry.get_tools_for_agent(
        permitted_tools=["*"],
        connected_integrations=["hubspot", "slack", "github"],
    )
    names = {t["function"]["name"] for t in tools}
    assert "hubspot_create_contact" in names
    assert "github_create_issue" in names


def test_openai_tool_shape(registry: ToolRegistry):
    spec = registry.get_spec("hubspot_search_contacts")
    assert spec is not None
    tool = spec.to_openai_tool()
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "hubspot_search_contacts"
    assert "query" in tool["function"]["parameters"]["properties"]


@pytest.mark.asyncio
async def test_execute_unknown_tool(registry: ToolRegistry, tool_ctx: ToolContext):
    result = await registry.execute_tool(ctx=tool_ctx, tool_name="not_a_tool", args={})
    assert result["success"] is False
    assert "Unknown tool" in result["error"]


@pytest.mark.asyncio
async def test_execute_web_search_not_configured(registry: ToolRegistry, tool_ctx: ToolContext):
    result = await registry.execute_tool(
        ctx=tool_ctx,
        tool_name="web_search",
        args={"query": "latest news"},
    )
    assert result["success"] is False
    assert result["query"] == "latest news"
    assert "TAVILY_API_KEY" in result["error"]


@pytest.mark.asyncio
async def test_execute_web_search_missing_query(registry: ToolRegistry, tool_ctx: ToolContext):
    result = await registry.execute_tool(
        ctx=tool_ctx,
        tool_name="web_search",
        args={"query": "   "},
    )
    assert result["success"] is False
    assert "query" in result["error"].lower()


@pytest.mark.asyncio
async def test_execute_web_search_success(registry: ToolRegistry, tool_ctx: ToolContext):
    mock_payload = {
        "results": [{"title": "Example", "url": "https://example.com", "snippet": "Snippet"}],
        "sources": [{"title": "Example", "url": "https://example.com", "excerpt": "Snippet"}],
        "totalResults": 1,
    }
    with patch("app.services.web_research.search_web", new=AsyncMock(return_value=mock_payload)):
        result = await registry.execute_tool(
            ctx=tool_ctx,
            tool_name="web_search",
            args={"query": "latest news"},
        )
    assert result["success"] is True
    assert result["totalResults"] == 1
    assert result["results"][0]["title"] == "Example"


@pytest.mark.asyncio
async def test_execute_maps_hubspot_search_and_invokes(registry: ToolRegistry, tool_ctx: ToolContext):
    expected = NormalizedResult(
        success=True,
        action="hubspot.contacts.search",
        data={"contacts": [{"id": "1"}]},
        connector_id="conn-hs",
    )
    with patch("app.services.tool_registry.invoke_tool", return_value=expected) as mock_invoke:
        result = await registry.execute_tool(
            ctx=tool_ctx,
            tool_name="hubspot_search_contacts",
            args={"query": "acme@example.com", "limit": 5},
        )
    assert result["success"] is True
    assert result["result"]["contacts"][0]["id"] == "1"
    mock_invoke.assert_called_once()
    _ctx, action, params = mock_invoke.call_args[0]
    assert action == "hubspot.contacts.search"
    assert params["limit"] == 5
    assert params["filter_groups"][0]["filters"][0]["value"] == "acme@example.com"


@pytest.mark.asyncio
async def test_execute_salesforce_update_routes_by_object_type(
    registry: ToolRegistry, tool_ctx: ToolContext
):
    expected = NormalizedResult(
        success=True,
        action="salesforce.opportunities.update",
        data={"id": "opp-1"},
    )
    with patch("app.services.tool_registry.invoke_tool", return_value=expected) as mock_invoke:
        result = await registry.execute_tool(
            ctx=tool_ctx,
            tool_name="salesforce_update_record",
            args={
                "object_type": "Opportunity",
                "record_id": "opp-1",
                "fields": {"StageName": "Closed Won"},
            },
        )
    assert result["success"] is True
    _ctx, action, params = mock_invoke.call_args[0]
    assert action == "salesforce.opportunities.update"
    assert params["opportunity_id"] == "opp-1"


@pytest.mark.asyncio
async def test_execute_github_repo_parsing(registry: ToolRegistry, tool_ctx: ToolContext):
    expected = NormalizedResult(success=True, action="github.issues.create", data={"issue": {}})
    with patch("app.services.tool_registry.invoke_tool", return_value=expected) as mock_invoke:
        await registry.execute_tool(
            ctx=tool_ctx,
            tool_name="github_create_issue",
            args={"repo": "gravitre/operator", "title": "Bug"},
        )
    _ctx, _action, params = mock_invoke.call_args[0]
    assert params["owner"] == "gravitre"
    assert params["repo"] == "operator"


def test_get_handler_returns_execute_for_known_tool(registry: ToolRegistry):
    handler = registry.get_handler("slack_send_message")
    assert handler is not None
    assert handler.__name__ == "execute_tool"


def test_get_handler_unknown(registry: ToolRegistry):
    assert registry.get_handler("missing") is None


def test_singleton():
    assert get_tool_registry() is get_tool_registry()


def test_list_connected_integrations(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.connectors.connector_availability_service.list_executable_integrations",
        lambda *_args, **_kwargs: ["hubspot", "github"],
    )
    connected = ToolRegistry.list_connected_integrations(MagicMock(), "org-1")
    assert set(connected) == {"github", "hubspot"}
