"""Least-privilege tool and connector selection for classified tasks."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.services.tool_registry import ToolRegistry
from app.services.domain_routing_policy import apply_tool_selection_policy
from app.services.learning_strategy_keys import parse_segment_key
from app.workflows.repository import get_supabase_client


class ToolConnectorSelector:
    """Filters ToolRegistry tools to task-relevant read/write scopes."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._registry = ToolRegistry()

    async def select_for_task(
        self,
        org_id: str,
        classification: dict[str, Any],
        agent_persona: dict[str, Any],
        *,
        environment_name: str = "production",
    ) -> dict[str, Any]:
        client = get_supabase_client(self.settings)
        connected = self._registry.list_connected_integrations(
            client, org_id, environment_name=environment_name
        )
        preferred = set(agent_persona.get("preferred_connectors") or [])
        all_tools = await self._registry.get_available_tools(org_id, [], list(connected))

        def _connector_name(tool: dict[str, Any]) -> str:
            fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
            name = str(fn.get("name") or tool.get("name") or "")
            return name.split("_", 1)[0].lower() if "_" in name else name.lower()

        task_tools = [
            tool
            for tool in all_tools
            if _connector_name(tool) in preferred or tool.get("always_available")
        ]
        read_tools = [
            tool
            for tool in task_tools
            if str(tool.get("capability_tier") or "read").lower() != "write"
        ]
        write_tools = [
            tool
            for tool in task_tools
            if str(tool.get("capability_tier") or "").lower() == "write"
            or tool.get("requires_approval") is True
        ]
        result = {
            "read_tools": read_tools,
            "write_tools": write_tools,
            "write_requires_approval": len(write_tools) > 0,
            "tool_count": len(task_tools),
        }
        routed = apply_tool_selection_policy(result, classification, agent_persona)
        from app.services.meta_learning_service import get_meta_learning_service

        meta = get_meta_learning_service(self.settings)
        if meta.is_enabled():
            segment_key = parse_segment_key(classification)
            connectors = list(agent_persona.get("preferred_connectors") or [])
            combo_key = meta.build_connector_combo_key(connectors)
            guidance = await meta.get_selection_guidance(
                org_id,
                segment_key,
                "connector_combo",
                [combo_key],
                default_key=combo_key,
                classification=classification,
            )
            routed = meta.apply_tool_soft_prior(routed, guidance)
        return routed


_tool_connector_selector: ToolConnectorSelector | None = None


def get_tool_connector_selector(settings: Settings | None = None) -> ToolConnectorSelector:
    global _tool_connector_selector
    if _tool_connector_selector is None or settings is not None:
        _tool_connector_selector = ToolConnectorSelector(settings)
    return _tool_connector_selector
