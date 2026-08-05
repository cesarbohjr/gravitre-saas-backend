"""G.5.2 progressive disclosure + write-authority still after full schema load."""
from __future__ import annotations

from app.services.progressive_tool_schemas import (
    SEARCH_CATALOG_TOOLS_NAME,
    apply_progressive_disclosure,
    execute_search_catalog_tools,
    gate_deferred_tool_call,
    payload_bytes,
    to_stub,
)
from app.services.react_write_gate import tool_requires_user_write_approval
from app.services.tool_registry import get_tool_registry


def _sample_write_tool() -> dict:
    registry = get_tool_registry()
    for name in ("hubspot_lists_create", "apollo_lists_add", "hubspot_lists_add_contact"):
        spec = registry._specs.get(name)  # noqa: SLF001
        if spec is not None:
            return spec.to_openai_tool()
    # Fallback synthetic write-shaped tool
    return {
        "type": "function",
        "function": {
            "name": "hubspot_lists_create",
            "description": "Create a HubSpot list. Use when you need a new static list.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    }


def test_stubs_are_smaller_than_full_schemas():
    registry = get_tool_registry()
    tools = registry.get_tools_for_agent(["*"], ["apollo", "hubspot", "platform"])[:16]
    attach, full_by_name, loaded = apply_progressive_disclosure(tools)
    assert loaded == set()
    assert SEARCH_CATALOG_TOOLS_NAME in {
        str((t.get("function") or {}).get("name") or "") for t in attach
    }
    stubs_only = [t for t in attach if t.get("gravitre_deferred")]
    stub_bytes = payload_bytes(stubs_only)
    full_bytes = payload_bytes(list(full_by_name.values()))
    assert stub_bytes < full_bytes
    # Deferred stubs (empty parameters) must beat full schemas by a clear margin.
    ratio = stub_bytes / max(1, full_bytes)
    assert ratio < 0.65, f"stub/full ratio={ratio:.3f} stub={stub_bytes} full={full_bytes}"


def test_write_using_only_stub_is_rejected_until_full_schema_loaded():
    """HARD REQUIREMENT: progressive stubs cannot bypass write authority path."""
    write_tool = _sample_write_tool()
    name = write_tool["function"]["name"]
    attach, full_by_name, loaded = apply_progressive_disclosure([write_tool])
    allowed, reason = gate_deferred_tool_call(
        name, loaded_names=loaded, full_by_name=full_by_name
    )
    assert allowed is False
    assert reason == "full_schema_not_loaded"

    loaded, result = execute_search_catalog_tools(
        {"tool_names": [name]},
        full_by_name=full_by_name,
        loaded_names=loaded,
    )
    assert name in loaded
    assert result["count"] == 1
    allowed, reason = gate_deferred_tool_call(
        name, loaded_names=loaded, full_by_name=full_by_name
    )
    assert allowed is True
    assert reason == "loaded"

    # After full schema load, catalog write authority STILL applies.
    registry = get_tool_registry()
    requires_write, *_ = tool_requires_user_write_approval(name, registry)
    assert requires_write is True


def test_to_stub_strips_parameters():
    full = _sample_write_tool()
    stub = to_stub(full)
    assert stub.get("gravitre_deferred") is True
    params = stub["function"]["parameters"]
    assert params.get("properties") == {}
    assert "required" not in params or not params.get("required")
