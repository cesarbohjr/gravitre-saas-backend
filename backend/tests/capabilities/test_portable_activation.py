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


def test_unsupported_external_components_remain_inert() -> None:
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
    assert by_kind["agent"]["supportedActivation"] is False
    assert by_kind["play"]["supportedActivation"] is False
    assert plan["unsupportedDeclarationsRemainInert"] is True
