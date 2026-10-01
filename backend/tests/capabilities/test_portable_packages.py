from app.capabilities.packages import inspect_package, installation_allowed


def test_agent_skill_is_detected_and_low_risk_without_execution() -> None:
    result = inspect_package(
        {"name": "SEO analyst", "license": "Apache-2.0"},
        skill_md="---\nname: seo-analyst\ndescription: Analyze SEO data\n---\nUse evidence.",
    )
    assert result.format == "agent_skill"
    assert result.license_policy == "allow"
    assert result.risk == "low"
    assert installation_allowed(result)


def test_write_capable_plugin_is_never_treated_as_unrestricted() -> None:
    result = inspect_package(
        {
            "name": "CRM operator",
            "license": "MIT",
            "permissions": ["contacts.read", "contacts.write"],
            "mcpServers": {"crm": {"url": "https://mcp.example.com"}},
        }
    )
    assert result.has_write_tools
    assert result.risk == "moderate"
    assert "mcp.example.com" in result.network_hosts


def test_executable_remote_package_is_high_risk() -> None:
    result = inspect_package(
        {
            "name": "automation",
            "license": "MIT",
            "permissions": ["records.write"],
            "hooks": [{"name": "after", "command": "python hook.py"}],
            "mcpServers": {"remote": {"url": "https://tools.example.com/mcp"}},
        }
    )
    assert result.has_executable_code
    assert result.risk == "high"


def test_proprietary_redistribution_restriction_blocks_install() -> None:
    result = inspect_package(
        {"name": "restricted", "license": "Proprietary - no redistribution"}
    )
    assert result.license_policy == "block"
    assert result.risk == "blocked"
    assert not installation_allowed(result)
