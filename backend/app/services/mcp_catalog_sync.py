"""Sync discovered MCP tools into the vendor catalog extension registry."""
from __future__ import annotations

import re
from typing import Any

from app.connectors.action_catalog.builder import action
from app.connectors.action_catalog.extensions import register_vendor_extension
from app.connectors.action_catalog.models import VendorCatalogSpec
from app.services.mcp_client_service import classify_mcp_tool_capability, mcp_openai_tool_name


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_") or "tool"


def vendor_slug_for_mcp_server(server_name: str, server_id: str) -> str:
    base = _slug(server_name) or _slug(server_id)
    return f"mcp_{base}"[:48]


def build_mcp_vendor_catalog(
    *,
    server_name: str,
    server_id: str,
    tools: list[dict[str, Any]],
) -> tuple[str, Any]:
    """Build a VendorCatalogSpec from discovered MCP tool rows."""
    vendor = vendor_slug_for_mcp_server(server_name, server_id)
    v1: list[Any] = []
    v2: list[Any] = []
    v3: list[Any] = []
    for row in tools:
        tool_name = str(row.get("tool_name") or row.get("name") or "").strip()
        if not tool_name:
            continue
        description = str(row.get("tool_description") or row.get("description") or tool_name)
        capability = str(row.get("capability_tier") or classify_mcp_tool_capability(tool_name, description))
        suffix = _slug(tool_name)
        openai_name = mcp_openai_tool_name(server_name, tool_name)
        spec = action(
            vendor,
            suffix,
            tool_name.replace("_", " ").title(),
            tier="v1" if capability == "read" else "v2",
            kind="read" if capability == "read" else "write",
            scope_suffix=f"tools:{capability}",
            description=f"{description} (MCP via {server_name}; invoke as `{openai_name}`)",
            requires_approval=capability == "write",
            destructive=capability == "write",
        )
        if capability == "read":
            v1.append(spec)
        elif capability == "write":
            v2.append(spec)
        else:
            v3.append(spec)
    catalog = VendorCatalogSpec(
        vendor=vendor,
        display_name=f"MCP · {server_name}",
        category="MCP Extension",
        api_docs_url="https://modelcontextprotocol.io/",
        shipped=True,
        v1=tuple(v1),
        v2=tuple(v2),
        v3=tuple(v3),
        demo_workflows=(),
    )
    return vendor, catalog


def sync_mcp_server_to_catalog(
    *,
    server_name: str,
    server_id: str,
    tools: list[dict[str, Any]],
) -> str:
    """Register or replace MCP server tools in the catalog extension layer."""
    vendor, catalog = build_mcp_vendor_catalog(
        server_name=server_name,
        server_id=server_id,
        tools=tools,
    )
    # Replace prior extension for the same vendor slug.
    from app.connectors.action_catalog import extensions as ext_module

    ext_module.VENDOR_CATALOG_EXTENSIONS = tuple(
        spec for spec in ext_module.VENDOR_CATALOG_EXTENSIONS if spec.vendor != vendor
    )
    register_vendor_extension(catalog)
    return vendor
