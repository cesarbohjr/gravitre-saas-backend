from app.capabilities.activation import build_activation_plan


def test_mcp_dependencies_map_to_existing_governance_without_auto_activation() -> None:
    plan = build_activation_plan(
        {"mcpServers": {"crm": {"url": "https://mcp.example.com", "transport": "http"}}},
        {"risk": "moderate", "components": []},
    )
    assert plan["executionOwner"] == "gravitre"
    assert plan["directImportedCodeExecution"] is False
    assert plan["mcpServers"][0]["activation"] == "admin_review_required"
    assert plan["writePolicy"]["providerAcceptanceIsSuccess"] is False


def test_agent_and_play_declarations_require_native_admin_bindings() -> None:
    plan = build_activation_plan(
        {"agents": [{"name": "Researcher"}], "plays": [{"name": "Growth play"}]},
        {
            "risk": "low",
            "components": [
                {"kind": "agent", "name": "Researcher", "executable": False},
                {"kind": "play", "name": "Growth play", "executable": False},
            ],
        },
    )
    by_kind = {row["kind"]: row for row in plan["components"]}
    assert by_kind["agent"]["supportedActivation"] is True
    assert by_kind["agent"]["activation"] == "admin_bind_to_existing_agent"
    assert by_kind["play"]["supportedActivation"] is True
    assert by_kind["play"]["activation"] == "admin_bind_to_existing_play_or_workflow"
    assert plan["directImportedCodeExecution"] is False
    assert plan["unsupportedDeclarationsRemainInert"] is True
