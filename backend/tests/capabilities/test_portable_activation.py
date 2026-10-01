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
