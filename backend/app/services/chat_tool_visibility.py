"""Single source of truth for chat-visible connector tool names.

Both the NL phrase mapper and ReAct/unified paths must agree on which
registry tools are exposed to Gravitre chat for a connected org.
"""
from __future__ import annotations

from functools import lru_cache

from app.services.chat_tool_bridge import build_dynamic_chat_tool_specs
from app.services.connector_execution_matrix import chat_executable_entries

_SYNTHETIC_INTEGRATIONS = frozenset({"platform", "mcp", "browser", "webhook", "email"})


@lru_cache(maxsize=64)
def _dynamic_registry_keys() -> frozenset[str]:
    return frozenset(build_dynamic_chat_tool_specs().keys())


def chat_visible_connector_tool_names(
    *,
    connected_integrations: list[str] | None = None,
) -> frozenset[str]:
    """Tool names chat may invoke via mapper or ReAct (pre per-turn narrowing)."""
    dynamic = _dynamic_registry_keys()
    names: set[str] = set()
    for entry in chat_executable_entries(connected_integrations=connected_integrations):
        key = entry.tool_registry_key
        if key in dynamic:
            names.add(key)

    from app.services.tool_registry import get_tool_registry

    connected = [str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()]
    if "platform" not in connected:
        connected.append("platform")
    registry = get_tool_registry()
    for tool in registry.get_tools_for_agent(["*"], connected):
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
        name = str(fn.get("name") or tool.get("name") or "").strip()
        if not name:
            continue
        if name.startswith("assistant_") or name.startswith("browser_") or name == "web_search":
            continue
        integration = name.split("_", 1)[0].lower() if "_" in name else name.lower()
        if integration in _SYNTHETIC_INTEGRATIONS:
            continue
        names.add(name)
    return frozenset(names)
