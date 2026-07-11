"""Assistant intelligence mode resolution."""
from __future__ import annotations

from app.operators.assistant_mode_config import (
    normalize_mode,
    resolve_effective_intelligence_mode,
)


def test_normalize_mode_maps_deep_to_agent():
    assert normalize_mode("deep") == "agent"
    assert normalize_mode("standard") == "standard"


def test_resolve_upgrades_to_agent_when_connectors_connected():
    assert resolve_effective_intelligence_mode("standard", ["hubspot"]) == "agent"
    assert resolve_effective_intelligence_mode("deep", ["slack"]) == "agent"


def test_resolve_keeps_fast_when_connectors_connected():
    """Wave 4 — FAST must not silently upgrade to agent."""
    assert resolve_effective_intelligence_mode("fast", ["hubspot", "slack"]) == "fast"
    assert resolve_effective_intelligence_mode("fast", ["apollo"], has_mcp_tools=True) == "fast"


def test_resolve_keeps_agent_without_connectors():
    assert resolve_effective_intelligence_mode("deep", []) == "agent"
    assert resolve_effective_intelligence_mode("agent", []) == "agent"


def test_resolve_ignores_platform_connectors_for_upgrade():
    assert resolve_effective_intelligence_mode("standard", ["platform", "webhook"]) == "standard"


def test_resolve_upgrades_to_agent_when_mcp_tools_only():
    assert resolve_effective_intelligence_mode("standard", [], has_mcp_tools=True) == "agent"
